import 'dart:io';

import 'package:flutter/material.dart';
import 'package:synkora_chat/synkora_chat.dart';

void main() {
  runApp(const ExampleApp());
}

class ExampleApp extends StatelessWidget {
  const ExampleApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Synkora Chat Example',
      theme: ThemeData(
        colorSchemeSeed: Colors.indigo,
        useMaterial3: true,
      ),
      home: const ConfigScreen(),
    );
  }
}

/// Config screen — enter widget key and base URL at runtime.
class ConfigScreen extends StatefulWidget {
  const ConfigScreen({super.key});

  @override
  State<ConfigScreen> createState() => _ConfigScreenState();
}

class _ConfigScreenState extends State<ConfigScreen> {
  // Android emulator reaches host machine on 10.0.2.2; iOS Simulator uses localhost.
  static String get _defaultBase {
    try {
      if (Platform.isAndroid) return 'http://10.0.2.2:5001';
    } catch (_) {}
    return 'http://127.0.0.1:5001';
  }

  late final TextEditingController _keyCtrl =
      TextEditingController(text: 'widget_kdxEpFd7CANxcYwIK8_Z3hQ9mEpHGkksZEusuerGba8');
  late final TextEditingController _urlCtrl =
      TextEditingController(text: _defaultBase);
  late final TextEditingController _userCtrl =
      TextEditingController(text: 'test_user_001');
  String? _connectionMessage;
  bool _isChecking = false;

  @override
  void dispose() {
    _keyCtrl.dispose();
    _urlCtrl.dispose();
    _userCtrl.dispose();
    super.dispose();
  }

  Future<void> _openChat() async {
    final key = _keyCtrl.text.trim();
    final url = _urlCtrl.text.trim();
    if (key.isEmpty || url.isEmpty) return;

    setState(() {
      _isChecking = true;
      _connectionMessage = null;
    });

    try {
      final client = SynkoraClient(widgetKey: key, baseUrl: url);
      final config = await client.loadConfig();
      client.dispose();

      if (!mounted) return;

      await Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => ChatScreen(
            widgetKey: key,
            baseUrl: url,
            userId: _userCtrl.text.trim().isEmpty ? null : _userCtrl.text.trim(),
          ),
        ),
      );

      setState(() {
        _connectionMessage = 'Connected to ${config.agentName} at $url';
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _connectionMessage = e.toString().replaceFirst('Exception: ', '');
      });
    } finally {
      if (mounted) {
        setState(() {
          _isChecking = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Synkora Chat — Test Harness')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Enter your widget key and API base URL to test the chat widget.',
              style: TextStyle(color: Color(0xFF6D675F)),
            ),
            const SizedBox(height: 24),
            TextField(
              controller: _keyCtrl,
              decoration: const InputDecoration(
                labelText: 'Widget Key',
                hintText: 'widget_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.key),
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _urlCtrl,
              decoration: const InputDecoration(
                labelText: 'API Base URL',
                hintText: 'http://127.0.0.1:5001',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.link),
              ),
              keyboardType: TextInputType.url,
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _userCtrl,
              decoration: const InputDecoration(
                labelText: 'User ID (optional)',
                hintText: 'user_123',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.person),
              ),
            ),
            const SizedBox(height: 32),
            FilledButton.icon(
              onPressed: _isChecking ? null : _openChat,
              icon: _isChecking
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.chat_bubble_outline),
              label: Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Text(
                  _isChecking ? 'Checking connection…' : 'Open Chat Widget',
                  style: const TextStyle(fontSize: 16),
                ),
              ),
            ),
            if (_connectionMessage != null) ...[
              const SizedBox(height: 16),
              _StatusCard(
                message: _connectionMessage!,
                isError: _connectionMessage!.startsWith('Cannot reach') ||
                    _connectionMessage!.startsWith('Synkora rejected') ||
                    _connectionMessage!.startsWith('Synkora responded'),
              ),
            ],
            const SizedBox(height: 16),
            const _InfoCard(),
          ],
        ),
      ),
    );
  }
}

class _InfoCard extends StatelessWidget {
  const _InfoCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFFFFAF1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0x1A171717)),
      ),
      child: const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Local dev tips', style: TextStyle(fontWeight: FontWeight.w600)),
          SizedBox(height: 4),
          Text('Flutter talks directly to the API, not the Next.js app.',
              style: TextStyle(fontSize: 12, color: Color(0xFF6D675F))),
          Text('Android emulator  →  http://10.0.2.2:5001',
              style: TextStyle(fontSize: 12, color: Color(0xFF6D675F))),
          Text('iOS Simulator/macOS →  http://127.0.0.1:5001',
              style: TextStyle(fontSize: 12, color: Color(0xFF6D675F))),
          Text('Start the API before opening chat.',
              style: TextStyle(fontSize: 12, color: Color(0xFF6D675F))),
        ],
      ),
    );
  }
}

class _StatusCard extends StatelessWidget {
  final String message;
  final bool isError;

  const _StatusCard({
    required this.message,
    required this.isError,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: isError ? const Color(0xFFFFF2EC) : const Color(0xFFEEF9F3),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isError ? const Color(0xFFF2D1BD) : const Color(0xFFB9EDD9),
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            isError ? Icons.wifi_off_rounded : Icons.check_circle_outline_rounded,
            size: 18,
            color: isError ? const Color(0xFFC45F34) : const Color(0xFF2D8B69),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: TextStyle(
                fontSize: 12,
                height: 1.5,
                color: isError ? const Color(0xFF8B3F1E) : const Color(0xFF225446),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class ChatScreen extends StatelessWidget {
  final String widgetKey;
  final String baseUrl;
  final String? userId;

  const ChatScreen({
    super.key,
    required this.widgetKey,
    required this.baseUrl,
    this.userId,
  });

  @override
  Widget build(BuildContext context) {
    return SynkoraChatWidget(
      widgetKey: widgetKey,
      baseUrl: baseUrl,
      userId: userId,
      onClose: () => Navigator.pop(context),
    );
  }
}
