import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

/// Minimal MJPEG viewer: reads the multipart stream and shows JPEG frames.
class MjpegView extends StatefulWidget {
  final String url;

  const MjpegView({super.key, required this.url});

  @override
  State<MjpegView> createState() => _MjpegViewState();
}

class _MjpegViewState extends State<MjpegView> {
  http.Client? _client;
  StreamSubscription? _sub;
  Uint8List? _lastFrame;
  bool _error = false;

  @override
  void initState() {
    super.initState();
    _start();
  }

  @override
  void didUpdateWidget(covariant MjpegView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.url != widget.url) _start();
  }

  void _start() {
    _stop();
    _client = http.Client();
    var buffer = <int>[];
    final req = http.Request('GET', Uri.parse(widget.url));
    _sub = _client!.send(req).asStream().listen((resp) {
      resp.stream.listen((chunk) {
        buffer.addAll(chunk);
        // extract latest full JPEG from buffer
        while (true) {
          final start = buffer.indexOf(0xFF);
          final hasSoi = start >= 0 &&
              start + 1 < buffer.length &&
              buffer[start + 1] == 0xD8;
          if (!hasSoi) {
            if (buffer.length > 512 * 1024) buffer.clear();
            break;
          }
          // find EOI
          int? eoi;
          for (int i = start + 2; i + 1 < buffer.length; i++) {
            if (buffer[i] == 0xFF && buffer[i + 1] == 0xD9) { eoi = i + 2; break; }
          }
          if (eoi == null) break;
          final frame = Uint8List.fromList(buffer.sublist(start, eoi));
          buffer.removeRange(0, eoi);
          if (mounted) setState(() => _lastFrame = frame);
        }
      }, onDone: () {
        if (mounted) setState(() => _error = true);
      }, onError: (_) {
        if (mounted) setState(() => _error = true);
      });
    }, onError: (_) {
      if (mounted) setState(() => _error = true);
    });
  }

  void _stop() {
    _sub?.cancel();
    _client?.close();
    _client = null;
    _sub = null;
  }

  @override
  void dispose() {
    _stop();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_error && _lastFrame == null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.videocam_off, size: 56, color: Colors.white24),
            const SizedBox(height: 12),
            const Text('Waiting for the camera stream…'),
            const SizedBox(height: 8),
            TextButton(onPressed: () { setState(() { _error = false; }); _start(); },
                child: const Text('Retry')),
          ],
        ),
      );
    }
    if (_lastFrame == null) {
      return const Center(child: CircularProgressIndicator());
    }
    return Image.memory(_lastFrame!, gaplessPlayback: true, fit: BoxFit.contain);
  }
}
