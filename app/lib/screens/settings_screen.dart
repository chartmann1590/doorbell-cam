import 'package:flutter/material.dart';

import '../hub_client.dart';

class SettingsScreen extends StatefulWidget {
  final HubClient hub;
  const SettingsScreen({super.key, required this.hub});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  Map<String, dynamic> _tuning = {};
  Map<String, dynamic> _cam = {};

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final t = await widget.hub.settings();
      if (mounted) setState(() => _tuning = t);
    } catch (_) {}
    try {
      final c = await widget.hub.cameraStatus();
      if (mounted) setState(() => _cam = c);
    } catch (_) {}
  }

  Future<void> _push(String key, Object value) async {
    setState(() => _tuning[key] = value);
    await widget.hub.setSetting(key, value);
  }

  Future<void> _pushCam(String variable, int val) async {
    setState(() => _cam[variable] = val);
    try {
      await widget.hub.cameraControl(variable, val);
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(backgroundColor: Colors.transparent, title: const Text('Settings')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Detection', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          _slider('Motion sensitivity', 'motion_sensitivity', 1, 100),
          _slider('Alert cooldown (s)', 'cooldown_seconds', 2, 120),
          _slider('Person confidence', 'person_confidence', 0.1, 0.95),
          _slider('Face match threshold', 'face_match_threshold', 0.2, 0.8),
          const SizedBox(height: 20),
          Text('Camera sensor (live)', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          _camSlider('JPEG quality', 'quality', 4, 63),
          _camSlider('Brightness', 'brightness', -2, 2),
          _camSlider('Contrast', 'contrast', -2, 2),
          _camSlider('Saturation', 'saturation', -2, 2),
          SwitchListTile(
            title: const Text('Flip vertical'),
            value: (_cam['vflip'] ?? 0) == 1,
            onChanged: (v) => _pushCam('vflip', v ? 1 : 0),
          ),
          SwitchListTile(
            title: const Text('Mirror horizontal'),
            value: (_cam['hmirror'] ?? 0) == 1,
            onChanged: (v) => _pushCam('hmirror', v ? 1 : 0),
          ),
          const SizedBox(height: 20),
          const Text(
            'The app finds the hub automatically on your home network '
            '(mDNS + subnet scan). Manual entry is remembered if needed.',
            style: TextStyle(color: Colors.white38, fontSize: 12),
          ),
        ],
      ),
    );
  }

  Widget _slider(String label, String key, num min, num max) {
    final value = (() {
      final v = _tuning[key];
      if (v is num) return v.toDouble();
      return (min + max) / 2;
    })();
    final int_ = max is int && min is int;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          Text(label), Text(value.toStringAsFixed(int_ ? 0 : 2)),
        ]),
        Slider(
          value: value.clamp(min.toDouble(), max.toDouble()).toDouble(),
          min: min.toDouble(),
          max: max.toDouble(),
          divisions: int_ ? (max - min).toInt() : null,
          onChanged: (v) => _push(key, int_ ? v.round() : double.parse(v.toStringAsFixed(2))),
        ),
      ],
    );
  }

  Widget _camSlider(String label, String variable, int min, int max) {
    final raw = _cam[variable];
    final value = (raw is num ? raw.toDouble() : ((min + max) / 2).toDouble());
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          Text(label), Text(value.toStringAsFixed(0)),
        ]),
        Slider(
          value: value.clamp(min.toDouble(), max.toDouble()),
          min: min.toDouble(),
          max: max.toDouble(),
          divisions: max - min,
          onChanged: (v) => _pushCam(variable, v.round()),
        ),
      ],
    );
  }
}
