/// Synkora Chat Flutter SDK.
///
/// Drop-in usage:
/// ```dart
/// SynkoraChatWidget(
///   widgetKey: 'wk_xxx',
///   baseUrl: 'https://your-synkora.com',
/// )
/// ```
///
/// Headless usage:
/// ```dart
/// final controller = SynkoraChatController(
///   client: SynkoraClient(widgetKey: 'wk_xxx', baseUrl: '...'),
/// );
/// await controller.init();
/// ```
library synkora_chat;

export 'src/client/models.dart';
export 'src/client/synkora_client.dart';
export 'src/controller/synkora_chat_controller.dart';
export 'src/ui/synkora_chat_widget.dart';
