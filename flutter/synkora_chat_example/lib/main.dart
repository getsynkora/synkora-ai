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
    return 'http://localhost:5001';
  }

  late final TextEditingController _keyCtrl =
      TextEditingController(text: 'widget_kdxEpFd7CANxcYwIK8_Z3hQ9mEpHGkksZEusuerGba8');
  late final TextEditingController _urlCtrl =
      TextEditingController(text: _defaultBase);
  late final TextEditingController _userCtrl =
      TextEditingController(text: 'test_user_001');

  @override
  void dispose() {
    _keyCtrl.dispose();
    _urlCtrl.dispose();
    _userCtrl.dispose();
    super.dispose();
  }

  void _openChat() {
    final key = _keyCtrl.text.trim();
    final url = _urlCtrl.text.trim();
    if (key.isEmpty || url.isEmpty) return;

    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ChatScreen(
          widgetKey: key,
          baseUrl: url,
          userId: _userCtrl.text.trim().isEmpty ? null : _userCtrl.text.trim(),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Synkora Chat — Test Harness')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Enter your Widget Key and Base URL to test the chat widget.',
              style: TextStyle(color: Colors.black54),
            ),
            const SizedBox(height: 24),
            TextField(
              controller: _keyCtrl,
              decoration: const InputDecoration(
                labelText: 'Widget Key',
                hintText: 'wk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.key),
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _urlCtrl,
              decoration: const InputDecoration(
                labelText: 'Base URL',
                hintText: 'http://localhost:5001',
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
              onPressed: _openChat,
              icon: const Icon(Icons.chat_bubble_outline),
              label: const Padding(
                padding: EdgeInsets.symmetric(vertical: 4),
                child: Text('Open Chat Widget', style: TextStyle(fontSize: 16)),
              ),
            ),
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
        color: Colors.indigo.shade50,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.indigo.shade100),
      ),
      child: const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Local dev tips', style: TextStyle(fontWeight: FontWeight.w600)),
          SizedBox(height: 4),
          Text('Android emulator  →  http://10.0.2.2:5001',
              style: TextStyle(fontSize: 12, color: Colors.black54)),
          Text('iOS Simulator     →  http://localhost:5001',
              style: TextStyle(fontSize: 12, color: Colors.black54)),
          Text('Get your widget key from the Synkora dashboard.',
              style: TextStyle(fontSize: 12, color: Colors.black54)),
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
