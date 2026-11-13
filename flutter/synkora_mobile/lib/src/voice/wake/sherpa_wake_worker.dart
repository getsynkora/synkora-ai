import 'dart:isolate';

import 'package:sherpa_onnx/sherpa_onnx.dart' as sherpa;

import 'wake_keywords.dart';

/// Everything the worker isolate needs to start; plain data so it can be sent
/// across the isolate boundary.
class WakeWorkerInit {
  const WakeWorkerInit({
    required this.reply,
    required this.modelDirectory,
    required this.sensitivity,
    this.nativeLibraryPath,
  });

  final SendPort reply;
  final String modelDirectory;
  final WakeSensitivity sensitivity;

  /// Only needed on desktop hosts (tests); phones load the library themselves.
  final String? nativeLibraryPath;
}

/// Entry point of the wake-word isolate.
///
/// Runs the keyword spotter off the UI thread. Protocol, from the owner:
///   `TransferableTypedData` (Float32 samples) - audio to listen to
///   `'reset'`                                  - forget partial matches
///   `int`                                      - new [WakeSensitivity] index
///   `'stop'`                                   - release everything and exit
/// and to the owner:
///   `SendPort`                                 - ready; send commands here
///   `'detected'`                               - the phrase was heard
///   `String` starting with `error:`            - could not start
void wakeWorkerMain(WakeWorkerInit init) {
  final inbox = ReceivePort();
  sherpa.KeywordSpotter? spotter;
  sherpa.OnlineStream? stream;
  var sensitivity = init.sensitivity;

  // The beam width is part of the model configuration, so a new sensitivity
  // means a new spotter (cheap: the model is a few megabytes).
  void build() {
    stream?.free();
    spotter?.free();
    final dir = init.modelDirectory;
    final keywords = buildWakeKeywords(sensitivity);
    spotter = sherpa.KeywordSpotter(
      sherpa.KeywordSpotterConfig(
        model: sherpa.OnlineModelConfig(
          transducer: sherpa.OnlineTransducerModelConfig(
            encoder: '$dir/encoder.int8.onnx',
            decoder: '$dir/decoder.int8.onnx',
            joiner: '$dir/joiner.int8.onnx',
          ),
          tokens: '$dir/tokens.txt',
          numThreads: 1,
          debug: false,
        ),
        maxActivePaths: sensitivity.maxActivePaths,
        keywordsScore: sensitivity.score,
        keywordsThreshold: sensitivity.threshold,
        keywordsBuf: keywords,
        keywordsBufSize: keywords.length,
      ),
    );
    stream = spotter!.createStream();
  }

  try {
    sherpa.initBindings(init.nativeLibraryPath);
    build();
  } catch (e) {
    init.reply.send('error: $e');
    return;
  }

  init.reply.send(inbox.sendPort);

  inbox.listen((message) {
    if (message is TransferableTypedData) {
      final samples = message.materialize().asFloat32List();
      final s = stream!;
      final k = spotter!;
      s.acceptWaveform(samples: samples, sampleRate: 16000);
      while (k.isReady(s)) {
        k.decode(s);
        if (k.getResult(s).keyword.isNotEmpty) {
          init.reply.send('detected');
          k.reset(s);
        }
      }
    } else if (message == 'reset') {
      stream?.free();
      stream = spotter!.createStream();
    } else if (message is int) {
      sensitivity = WakeSensitivity.values[message];
      build();
    } else if (message == 'stop') {
      stream?.free();
      spotter?.free();
      inbox.close();
    }
  });
}
