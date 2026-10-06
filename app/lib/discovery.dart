import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'hub_client.dart';

/// Finds the DoorbellCam hub without manual setup:
/// 1. mDNS query for `doorbellhub.local` (raw UDP — no native plugin needed)
/// 2. subnet scan of the phone's /24 for the hub marker
/// 3. last remembered address / manual entry
class HubDiscovery {
  static const String _prefKey = 'hub_endpoint';

  /// Returns "host:port" of the hub or null.
  static Future<String?> discover({Duration timeout = const Duration(seconds: 6)}) async {
    final prefs = await SharedPreferences.getInstance();
    final remembered = prefs.getString(_prefKey);

    // 1) mDNS
    final mdns = await _queryMdns('doorbellhub.local', timeout);
    if (mdns != null && await _isHub(mdns)) {
      await prefs.setString(_prefKey, mdns);
      return mdns;
    }

    // 2) subnet scan
    final scanned = await _scanSubnet(timeout);
    if (scanned != null) {
      await prefs.setString(_prefKey, scanned);
      return scanned;
    }

    // 3) remembered (works even if discovery is blocked; may be stale)
    return remembered;
  }

  static Future<void> saveManual(String host, int port) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_prefKey, '$host:$port');
  }

  static Future<String?> getSaved() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_prefKey);
  }

  static Future<bool> _isHub(String endpoint) async {
    final parts = endpoint.split(':');
    final host = parts[0];
    final port = parts.length > 1 ? int.tryParse(parts[1]) ?? defaultPort : defaultPort;
    return HubClient(host, port: port).ping();
  }

  /// Resolve an mDNS .local name via a one-shot multicast DNS query.
  static Future<String?> _queryMdns(String fqdn, Duration timeout) async {
    RawDatagramSocket? socket;
    StreamSubscription<RawSocketEvent>? sub;
    try {
      socket = await RawDatagramSocket.bind('0.0.0.0', 0, reuseAddress: true);
      socket.joinMulticast(InternetAddress('224.0.0.251'));
      socket.send(_buildQuery(fqdn), InternetAddress('224.0.0.251'), 5353);

      final completer = Completer<String?>();
      final timer = Timer(timeout, () {
        if (!completer.isCompleted) completer.complete(null);
      });

      sub = socket.listen((event) {
        if (event != RawSocketEvent.read) return;
        final dg = socket!.receive();
        if (dg == null) return;
        final ip = _firstARecord(dg.data);
        if (ip != null && !completer.isCompleted) {
          completer.complete(ip);
          timer.cancel();
        }
      });

      final ip = await completer.future;
      return ip != null ? '$ip:$defaultPort' : null;
    } catch (_) {
      return null;
    } finally {
      await sub?.cancel();
      socket?.close();
    }
  }

  /// Build a minimal DNS A-record query packet for `fqdn`.
  static Uint8List _buildQuery(String fqdn) {
    final bytes = BytesBuilder();
    bytes.add([0x00, 0x01, 0x01, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]);
    for (final label in fqdn.split('.')) {
      if (label.isEmpty) continue;
      bytes.add([label.length]);
      bytes.add(label.codeUnits);
    }
    bytes.add([0x00, 0x00, 0x01, 0x00, 0x01]); // root + type A + class IN
    return bytes.toBytes();
  }

  /// Parse the first A record (type 1, rdlength 4) from a DNS response.
  static String? _firstARecord(Uint8List d) {
    if (d.length < 12) return null;
    int i = 12;
    final questions = (d[4] << 8) | d[5];
    for (int q = 0; q < questions; q++) {
      i = _skipName(d, i);
      i += 4; // type + class
      if (i > d.length) return null;
    }
    final answers = (d[6] << 8) | d[7];
    for (int a = 0; a < answers; a++) {
      i = _skipName(d, i);
      if (i + 10 > d.length) return null;
      final type = (d[i] << 8) | d[i + 1];
      i += 8; // type(2) + class(2) + ttl(4)
      if (i + 2 > d.length) return null;
      final rdlen = (d[i] << 8) | d[i + 1];
      i += 2;
      if (type == 1 && rdlen == 4 && i + 4 <= d.length) {
        return '${d[i]}.${d[i + 1]}.${d[i + 2]}.${d[i + 3]}';
      }
      i += rdlen;
    }
    return null;
  }

  /// Skip a (possibly compressed) DNS name; returns index after it.
  static int _skipName(Uint8List d, int i) {
    while (i < d.length) {
      final len = d[i];
      if (len == 0) return i + 1;
      if (len & 0xC0 == 0xC0) return i + 2; // compression pointer
      i += len + 1;
    }
    return i;
  }

  static Future<String?> _scanSubnet(Duration timeout) async {
    final interfaces = await NetworkInterface.list();
    String? subnetBase;
    for (final itf in interfaces) {
      for (final addr in itf.addresses) {
        if (addr.type == InternetAddressType.IPv4 && !addr.isLoopback) {
          final octets = addr.address.split('.');
          if (octets.length == 4) {
            subnetBase = '${octets[0]}.${octets[1]}.${octets[2]}';
          }
        }
      }
    }
    if (subnetBase == null) return null;

    final found = Completer<String?>();
    final timer = Timer(timeout, () {
      if (!found.isCompleted) found.complete(null);
    });
    final client = http.Client();
    int pending = 0;

    Future<void> probe(String ip) async {
      try {
        final r = await client
            .get(Uri.parse('http://$ip:$defaultPort/api/hub-info'))
            .timeout(const Duration(milliseconds: 450));
        if (!found.isCompleted &&
            r.statusCode == 200 &&
            r.body.contains('"product":"doorbellhub"')) {
          found.complete('$ip:$defaultPort');
        }
      } catch (_) {
        // unreachable host — expected for most of the subnet
      } finally {
        pending--;
        if (pending == 0 && !found.isCompleted) found.complete(null);
      }
    }

    for (int i = 1; i <= 254; i++) {
      pending++;
      unawaited(probe('$subnetBase.$i'));
    }

    final result = await found.future;
    timer.cancel();
    client.close();
    return result;
  }
}
