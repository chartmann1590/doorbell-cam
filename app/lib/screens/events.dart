import 'package:flutter/material.dart';

import '../hub_client.dart';

class EventsScreen extends StatefulWidget {
  final HubClient hub;
  const EventsScreen({super.key, required this.hub});

  @override
  State<EventsScreen> createState() => _EventsScreenState();
}

class _EventsScreenState extends State<EventsScreen> {
  List<HubEvent> _events = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final evs = await widget.hub.events(limit: 100);
      if (mounted) setState(() { _events = evs; _loading = false; });
    } catch (_) {
      if (mounted) setState(() => _loading = false);
    }
  }

  IconData _icon(String kind) => switch (kind) {
        'face' => Icons.face,
        'person' => Icons.directions_walk,
        'doorbell' => Icons.doorbell,
        _ => Icons.waves,
      };

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        title: const Text('Alerts'),
        actions: [
          IconButton(onPressed: _load, icon: const Icon(Icons.refresh)),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _events.isEmpty
              ? const Center(child: Text('No alerts yet.'))
              : ListView.separated(
                  padding: const EdgeInsets.all(12),
                  itemCount: _events.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 8),
                  itemBuilder: (context, i) {
                    final ev = _events[i];
                    return Card(
                      child: ListTile(
                        leading: ClipRRect(
                          borderRadius: BorderRadius.circular(8),
                          child: ev.id > 0
                              ? Image.network(widget.hub.snapshotUrl(ev.id),
                                  width: 56, height: 56, fit: BoxFit.cover,
                                  errorBuilder: (_, __, ___) =>
                                      const SizedBox(width: 56, height: 56))
                              : Icon(_icon(ev.kind)),
                        ),
                        title: Text(ev.label.isNotEmpty ? ev.label : ev.kind),
                        subtitle: Text(
                            '${ev.ts.toLocal().toString().substring(0, 19)} · ${(ev.confidence * 100).toStringAsFixed(0)}%'),
                        trailing: Icon(_icon(ev.kind)),
                      ),
                    );
                  },
                ),
    );
  }
}
