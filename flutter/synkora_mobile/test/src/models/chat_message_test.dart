import 'package:flutter_test/flutter_test.dart';
import 'package:synkora_mobile/src/models/synkora_models.dart';

void main() {
  group('ChatMessage.fromJson', () {
    test('parses attachments from API payloads', () {
      final message = ChatMessage.fromJson({
        'id': 'message-1',
        'role': 'assistant',
        'content': 'Here is the file you requested.',
        'created_at': '2026-06-05T12:00:00Z',
        'attachments': [
          {
            'file_id': 'file-1',
            'file_name': 'report.pdf',
            'file_type': 'application/pdf',
            'file_size': 1048576,
            'download_url': 'https://example.com/report.pdf',
          },
          {
            'file_id': 'file-2',
            'file_name': 'chart.png',
            'file_type': 'image/png',
            'file_size': 2048,
            'thumbnail_url': 'https://example.com/chart-thumb.png',
          },
        ],
      });

      expect(message.attachments, hasLength(2));
      expect(message.attachments.first.fileName, 'report.pdf');
      expect(message.attachments.first.isPdf, isTrue);
      expect(message.attachments.last.isImage, isTrue);
      expect(
        message.attachments.last.previewUrl,
        'https://example.com/chart-thumb.png',
      );
    });
  });

  group('formatByteSize', () {
    test('formats byte counts into readable units', () {
      expect(formatByteSize(0), '0 B');
      expect(formatByteSize(1024), '1 KB');
      expect(formatByteSize(1536), '1.5 KB');
      expect(formatByteSize(1048576), '1 MB');
    });
  });
}
