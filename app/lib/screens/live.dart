import 'dart:async';

import 'package:flutter/material.dart';

import '../hub_client.dart';
import '../mjpeg.dart';
import '../notify.dart';

class LiveScreen extends StatefulWidget {
  final HubClient hub;
  const LiveScreen({super.key, required this.hub});

  @override
  State<LiveScreen> createState() => _LiveScreenState();
}

class _LiveScreenState extends State<LiveScreen> {
  HubStatus? _status;
  late final Stream<Map<String, dynamic>> _alerts;
  final _streamKey = ValueKey<DateTime>(DateTime.now());

  @override
  void initState() {
    super.initState();
    _alerts = widget.hub.alertStream();
    _poll();
  }

  void _poll() async {
    while (mounted) {
      try {
        final s = await widget.hub.status();
        if (mounted) setState(() => _status = s);
      } catch (_) {}
      await Future.delayed(const Duration(seconds: 3));
    }
  }

  void _showAlert(BuildContext context, Map<String, dynamic> msg) {
    if (msg['kind'] == null) return; // hello message etc.
    final kind = msg['kind'] as String;
    final label = (msg['label'] ?? '') as String;
    final id = (msg['id'] ?? 0) as int;
    // Also raise a system notification (visible if the app is backgrounded
    // while the OS keeps the socket alive).
    Notify.showAlert(
      title: kind == 'face' ? 'Face detected: $label' : 'Person detected!',
      body: label.isNotEmpty ? label : 'Motion at your door',
    );
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      duration: const Duration(seconds: 5),
      behavior: SnackBarBehavior.floating,
      content: Row(children: [
        const Icon(Icons.notifications_active, color: Colors.amber),
        const SizedBox(width: 10),
        Expanded(child: Text(kind == 'face' ? 'Face detected: $label' : 'Person detected!')),
      ]),
      action: SnackBarAction(
        label: 'View',
        onPressed: () {
          showDialog(
            context: context,
            builder: (_) => AlertDialog(
              title: Text('$kind alert'),
              content: id > 0
                  ? Image.network(widget.hub.snapshotUrl(id))
                  : const Text('No snapshot'),
            ),
          );
        },
      ),
    ));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        title: const Text('DoorbellCam'),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 16),
            child: Center(
              child: Chip(
                avatar: Icon(
                  _status?.cameraOnline == true ? Icons.sensors : Icons.sensors_off,
                  size: 16,
                  color: _status?.cameraOnline == true ? Colors.greenAccent : Colors.redAccent,
                ),
                label: Text(
                  _status?.cameraOnline == true
                      ? 'camera ${_status?.cameraIp ?? ''}'
                      : 'camera offline',
                  style: const TextStyle(fontSize: 11),
                ),
              ),
            ),
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: Stack(
              alignment: Alignment.center,
              children: [
                MjpegView(url: widget.hub.streamUrl(), key: _streamKey),
                if (_status != null && _status!.personCount > 0)
                  Positioned(
                    top: 12,
                    left: 12,
                    child: Chip(
                      backgroundColor: Colors.red.shade900,
                      label: const Text('● Person detected'),
                    ),
                  ),
              ],
            ),
          ),
          StreamBuilder<Map<String, dynamic>>(
            stream: _alerts,
            builder: (context, snap) {
              if (snap.hasData) {
                WidgetsBinding.instance.addPostFrameCallback(
                    (_) => _showAlert(context, snap.data!));
              }
              return const SizedBox.shrink();
            },
          ),
        ],
      ),
    );
  }
}
