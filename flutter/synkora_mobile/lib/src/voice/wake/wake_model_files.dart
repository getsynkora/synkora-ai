import 'dart:io';

import 'package:flutter/services.dart';
import 'package:path_provider/path_provider.dart';

/// Makes the bundled wake-word model available as ordinary files, which is
/// what the native inference engine needs.
class WakeModelFiles {
  const WakeModelFiles._();

  static const _assetDir = 'assets/voice/wake';
  static const _names = [
    'encoder.int8.onnx',
    'decoder.int8.onnx',
    'joiner.int8.onnx',
    'tokens.txt',
  ];

  /// Bump when the bundled model changes so devices refresh their copy.
  static const _version = 1;

  /// Copies the model out of the app bundle (once) and returns its directory.
  static Future<String> ensure({AssetBundle? bundle}) async {
    final assets = bundle ?? rootBundle;
    final support = await getApplicationSupportDirectory();
    final dir = Directory('${support.path}/wake_model_v$_version');
    await dir.create(recursive: true);

    for (final name in _names) {
      final target = File('${dir.path}/$name');
      final data = await assets.load('$_assetDir/$name');
      final bytes = data.buffer.asUint8List(
        data.offsetInBytes,
        data.lengthInBytes,
      );
      // Re-copy if missing or truncated (for example an interrupted first run).
      if (!await target.exists() || await target.length() != bytes.length) {
        await target.writeAsBytes(bytes, flush: true);
      }
    }
    return dir.path;
  }
}
