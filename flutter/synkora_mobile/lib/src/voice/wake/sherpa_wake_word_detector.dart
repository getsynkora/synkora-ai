import 'dart:async';
import 'dart:collection';
import 'dart:isolate';
import 'dart:typed_data';

import '../ports.dart';
import 'sherpa_wake_worker.dart';
import 'wake_keywords.dart';
import 'wake_model_files.dart';

/// On-device "Hey Synkora" detection.
///
/// A tiny streaming speech model runs in a background isolate, so listening
/// never competes with the UI. Audio never leaves the phone. Frames fed to
/// [process] before the model has finished loading are held briefly and
/// replayed, so nothing said right after start-up is lost.
class SherpaWakeWordDetector
    implements WakeWordDetector, WakeWordStatus, WakeSensitivityControl {
  SherpaWakeWordDetector({
    WakeSensitivity sensitivity = WakeSensitivity.balanced,
    this.modelDirectory,
    this.nativeLibraryPath,
    this.cooldown = const Duration(milliseconds: 1800),
  }) : _sensitivity = sensitivity;

  /// Use an existing directory of model files instead of unpacking the bundled
  /// assets (tests, or a model downloaded separately).
  final String? modelDirectory;

  /// Explicit path to the native library; only needed outside a phone.
  final String? nativeLibraryPath;

  /// Ignore further detections for this long after one, so a single
  /// utterance cannot wake twice.
  final Duration cooldown;

  /// Frames kept while the model loads, then replayed (about 1.5 s).
  static const _maxBufferedFrames = 75;

  WakeSensitivity _sensitivity;
  Isolate? _isolate;
  SendPort? _worker;
  ReceivePort? _fromWorker;
  Future<void>? _starting;
  final Queue<Float32List> _pending = Queue();
  final StreamController<void> _detections = StreamController.broadcast();
  DateTime _quietUntil = DateTime.fromMillisecondsSinceEpoch(0);
  bool _detected = false;
  bool _disposed = false;
  String? _failure;

  @override
  String? get failure => _failure;

  @override
  bool get isReady => _worker != null;

  /// Emits when the phrase is heard (in addition to [process] returning true).
  Stream<void> get detections => _detections.stream;

  @override
  WakeSensitivity get sensitivity => _sensitivity;

  @override
  set sensitivity(WakeSensitivity value) {
    if (value == _sensitivity) return;
    _sensitivity = value;
    _worker?.send(value.index);
  }

  @override
  Future<void> start() => _starting ??= _start();

  Future<void> _start() async {
    if (_disposed) return;
    final port = ReceivePort();
    _fromWorker = port;
    try {
      final directory = modelDirectory ?? await WakeModelFiles.ensure();
      final ready = Completer<void>();
      port.listen((message) {
        if (message is SendPort) {
          _worker = message;
          if (!ready.isCompleted) ready.complete();
        } else if (message == 'detected') {
          _onDetected();
        } else if (message is String && message.startsWith('error:')) {
          _failure = message.substring(6).trim();
          if (!ready.isCompleted) ready.complete();
        }
      });
      _isolate = await Isolate.spawn(
        wakeWorkerMain,
        WakeWorkerInit(
          reply: port.sendPort,
          modelDirectory: directory,
          sensitivity: _sensitivity,
          nativeLibraryPath: nativeLibraryPath,
        ),
        errorsAreFatal: false,
      );
      await ready.future.timeout(const Duration(seconds: 20));
      final worker = _worker;
      if (worker != null) {
        while (_pending.isNotEmpty) {
          worker.send(TransferableTypedData.fromList([_pending.removeFirst()]));
        }
      }
    } catch (e) {
      _failure = e.toString();
    }
  }

  void _onDetected() {
    final now = DateTime.now();
    if (now.isBefore(_quietUntil)) return;
    _quietUntil = now.add(cooldown);
    _detected = true;
    if (!_detections.isClosed) _detections.add(null);
  }

  @override
  bool process(Int16List frame) {
    if (_disposed || _failure != null) return false;
    unawaited(start());

    final samples = Float32List(frame.length);
    for (var i = 0; i < frame.length; i++) {
      samples[i] = frame[i] / 32768.0;
    }
    final worker = _worker;
    if (worker != null) {
      worker.send(TransferableTypedData.fromList([samples]));
    } else {
      _pending.add(samples);
      if (_pending.length > _maxBufferedFrames) _pending.removeFirst();
    }

    if (_detected) {
      _detected = false;
      return true;
    }
    return false;
  }

  @override
  void reset() {
    _detected = false;
    _pending.clear();
    _worker?.send('reset');
  }

  @override
  Future<void> dispose() async {
    if (_disposed) return;
    _disposed = true;
    _worker?.send('stop');
    _isolate?.kill(priority: Isolate.beforeNextEvent);
    _fromWorker?.close();
    await _detections.close();
  }
}
