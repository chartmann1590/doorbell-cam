/// Typed HTTP + WebSocket client for the DoorbellCam hub.
///
/// [HubClient] wraps every REST endpoint the app needs (status, events,
/// settings, camera control, snapshots) plus the live `/api/ws` alert
/// stream. [HubEvent] and [HubStatus] parse the hub's JSON into
/// null-safe models. [defaultPort] (8765) matches the hub's `HUB_PORT`.
import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:web_socket_channel/web_socket_channel.dart';

const int defaultPort = 8765;

class HubEvent {
  final int id;
  final String kind; // person | face | motion | doorbell
  final String label;
  final double confidence;
  final DateTime ts;
  HubEvent({
    required this.id,
    required this.kind,
    required this.label,
    required this.confidence,
    required this.ts,
  });

  factory HubEvent.fromJson(Map<String, dynamic> j) => HubEvent(
        id: (j['id'] ?? 0) as int,
        kind: (j['kind'] ?? 'motion') as String,
        label: (j['label'] ?? '') as String,
        confidence: ((j['confidence'] ?? 0) as num).toDouble(),
        ts: DateTime.fromMillisecondsSinceEpoch(((j['ts'] ?? 0) as num).toInt() * 1000),
      );
}

class HubStatus {
  final bool cameraOnline;
  final String? cameraIp;
  final int personCount;
  final double motionLevel;
  final List<Map<String, dynamic>> faces;
  HubStatus({
    required this.cameraOnline,
    required this.cameraIp,
    required this.personCount,
    required this.motionLevel,
    required this.faces,
  });

  factory HubStatus.fromJson(Map<String, dynamic> j) => HubStatus(
        cameraOnline: (j['camera_online'] ?? false) as bool,
        cameraIp: j['camera_ip'] as String?,
        personCount: (j['person_count'] ?? 0) as int,
        motionLevel: ((j['motion_level'] ?? 0) as num).toDouble(),
        faces: ((j['faces'] ?? []) as List).cast<Map<String, dynamic>>(),
      );
}

class HubClient {
  final String host;
  final int port;
  String get base => 'http://$host:$port';
  Uri _u(String path) => Uri.parse('$base$path');

  HubClient(this.host, {this.port = defaultPort});

  Future<bool> ping() async {
    try {
      final r = await http.get(_u('/api/hub-info')).timeout(const Duration(seconds: 3));
      return r.statusCode == 200 && r.body.contains('doorbellhub');
    } catch (_) {
      return false;
    }
  }

  Future<HubStatus> status() async {
    final r = await http.get(_u('/api/status')).timeout(const Duration(seconds: 5));
    return HubStatus.fromJson(jsonDecode(r.body) as Map<String, dynamic>);
  }

  Future<List<HubEvent>> events({int limit = 50}) async {
    final r = await http.get(_u('/api/events?limit=$limit')).timeout(const Duration(seconds: 5));
    final list = jsonDecode(r.body) as List;
    return list.map((e) => HubEvent.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<Map<String, dynamic>> settings() async {
    final r = await http.get(_u('/api/settings')).timeout(const Duration(seconds: 5));
    return jsonDecode(r.body) as Map<String, dynamic>;
  }

  Future<void> setSetting(String key, Object value) async {
    await http.post(_u('/api/settings'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({key: value}));
  }

  Future<Map<String, dynamic>> cameraStatus() async {
    final r = await http.get(_u('/api/camera/status')).timeout(const Duration(seconds: 5));
    return jsonDecode(r.body) as Map<String, dynamic>;
  }

  Future<void> cameraControl(String variable, int val) async {
    await http.post(_u('/api/camera/control?var=$variable&val=$val'));
  }

  String streamUrl() => '$base/api/camera/stream';
  String snapshotUrl(int eventId) => '$base/api/events/$eventId/snapshot';

  WebSocketChannel connectWs() =>
      WebSocketChannel.connect(Uri.parse('ws://$host:$port/api/ws'));

  Stream<Map<String, dynamic>> alertStream() async* {
    final ws = connectWs();
    await for (final msg in ws.stream) {
      try {
        yield jsonDecode(msg as String) as Map<String, dynamic>;
      } catch (_) {}
    }
  }
}
