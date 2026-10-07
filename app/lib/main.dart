/// DoorbellCam companion app — entry point.
///
/// Shows [ConnectGate] first (auto-discovers the hub via mDNS / subnet
/// scan, with manual entry as fallback), then [HomeShell] with the three
/// main tabs: Live, Alerts, Settings. Notifications are initialized without
/// blocking first paint so the app never stalls on the permission dialog.
import 'dart:async';

import 'package:flutter/material.dart';

import 'discovery.dart';
import 'hub_client.dart';
import 'notify.dart';
import 'screens/live.dart';
import 'screens/events.dart';
import 'screens/settings_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const DoorbellApp());
  // Notification permission must not block first paint: awaiting it before
  // runApp left the first launch stuck on the system dialog with no UI.
  unawaited(Notify.init());
}

class DoorbellApp extends StatelessWidget {
  const DoorbellApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'DoorbellCam',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF0EA5E9),
          brightness: Brightness.dark,
        ),
        scaffoldBackgroundColor: const Color(0xFF070B14),
        cardTheme: CardThemeData(
          color: const Color(0xFF0F172A),
          elevation: 0,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        ),
      ),
      home: const ConnectGate(),
    );
  }
}

/// Auto-connects to the hub on start; manual entry as fallback.
class ConnectGate extends StatefulWidget {
  const ConnectGate({super.key});

  @override
  State<ConnectGate> createState() => _ConnectGateState();
}

class _ConnectGateState extends State<ConnectGate> {
  String _status = 'Looking for your DoorbellCam hub…';
  bool _busy = true;
  HubClient? _hub;

  @override
  void initState() {
    super.initState();
    _autoConnect();
  }

  Future<void> _autoConnect() async {
    setState(() { _busy = true; _status = 'Looking for your DoorbellCam hub…'; });
    final endpoint = await HubDiscovery.discover();
    if (endpoint != null) {
      final parts = endpoint.split(':');
      final hub = HubClient(parts[0],
          port: parts.length > 1 ? int.tryParse(parts[1]) ?? defaultPort : defaultPort);
      if (await hub.ping()) {
        setState(() { _hub = hub; _busy = false; });
        return;
      }
    }
    setState(() {
      _busy = false;
      _status = 'Hub not found automatically.\nEnter the address manually once — it is remembered.';
    });
  }

  Future<void> _manualConnect(String host, int port) async {
    final hub = HubClient(host, port: port);
    if (await hub.ping()) {
      await HubDiscovery.saveManual(host, port);
      setState(() { _hub = hub; });
    } else {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('No hub answered at $host:$port')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_hub != null) {
      return HomeShell(hub: _hub!);
    }
    return Scaffold(
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.doorbell_outlined, size: 72, color: Color(0xFF38BDF8)),
              const SizedBox(height: 24),
              Text(_status, textAlign: TextAlign.center),
              if (_busy) ...[
                const SizedBox(height: 24),
                const CircularProgressIndicator(),
              ] else ...[
                const SizedBox(height: 24),
                ManualEntryForm(onSubmit: _manualConnect),
                const SizedBox(height: 12),
                TextButton(onPressed: _autoConnect, child: const Text('Search again')),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class ManualEntryForm extends StatefulWidget {
  final void Function(String host, int port) onSubmit;
  const ManualEntryForm({super.key, required this.onSubmit});

  @override
  State<ManualEntryForm> createState() => _ManualEntryFormState();
}

class _ManualEntryFormState extends State<ManualEntryForm> {
  final _host = TextEditingController();
  final _port = TextEditingController(text: '$defaultPort');

  @override
  void dispose() {
    _host.dispose();
    _port.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        TextField(
          controller: _host,
          decoration: const InputDecoration(
            labelText: 'Hub address (e.g. 192.168.1.10)',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _port,
          keyboardType: TextInputType.number,
          decoration: const InputDecoration(
            labelText: 'Port',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 12),
        FilledButton(
          onPressed: () => widget.onSubmit(
              _host.text.trim(), int.tryParse(_port.text.trim()) ?? defaultPort),
          child: const Text('Connect'),
        ),
      ],
    );
  }
}

class HomeShell extends StatefulWidget {
  final HubClient hub;
  const HomeShell({super.key, required this.hub});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _tab = 0;
  late final List<Widget> _pages;

  @override
  void initState() {
    super.initState();
    _pages = [
      LiveScreen(hub: widget.hub),
      EventsScreen(hub: widget.hub),
      SettingsScreen(hub: widget.hub),
    ];
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _pages[_tab],
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) => setState(() => _tab = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.videocam_outlined), label: 'Live'),
          NavigationDestination(icon: Icon(Icons.notifications_outlined), label: 'Alerts'),
          NavigationDestination(icon: Icon(Icons.tune), label: 'Settings'),
        ],
      ),
    );
  }
}
