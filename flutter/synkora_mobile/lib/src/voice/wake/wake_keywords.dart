/// How eagerly the wake phrase triggers.
///
/// The presets are operating points measured against 24 synthetic voices
/// (144 phrase clips; 192 look-alike clips such as "hey Siri"; 192 sentences
/// that merely mention "Synkora" without "hey") and 26 minutes of continuous
/// speech. All three had no false wakes in that data; see
/// `assets/voice/wake/README.md`.
enum WakeSensitivity {
  /// Most conservative; roughly 70% of clear phrases are caught.
  low(maxActivePaths: 6, score: 2.0, threshold: 0.05),

  /// Default; roughly 84% of clear phrases are caught.
  balanced(maxActivePaths: 7, score: 2.5, threshold: 0.03),

  /// Catches roughly 86% but may very occasionally wake when the bare name is
  /// said without "hey".
  high(maxActivePaths: 6, score: 3.5, threshold: 0.03);

  const WakeSensitivity({
    required this.maxActivePaths,
    required this.score,
    required this.threshold,
  });

  /// How many alternative hypotheses the spotter tracks. Counter-intuitively
  /// more is not better: at 8 or more the bare name "Synkora" (no "hey")
  /// starts to wake it, and at 10 or more false wakes rise sharply.
  final int maxActivePaths;

  /// Boost given to each token of the phrase.
  final double score;

  /// Confidence needed to fire (lower is easier).
  final double threshold;
}

/// The label reported when the phrase is heard.
const String kWakeLabel = 'HEY_SYNKORA';

/// "Hey Synkora" as the model's subword units, in several pronunciations.
///
/// "Synkora" is a brand name the general-purpose model has never seen, so the
/// phrase is spelled the way it *sounds* ("sin-cora", "sink-ora", ...). Each
/// variant catches a different way people say it. Generated with
/// `sherpa-onnx-cli text2token --tokens-type bpe` from:
///
///   HEY SINCORA, HEY SYNCORA, HEY SINK ORA, HEY SINK CORA, HEY SYN KORA,
///   HEY SINKER A
const List<String> kWakeKeywordTokens = [
  '▁HE Y ▁S IN CO RA',
  '▁HE Y ▁S Y N CO RA',
  '▁HE Y ▁S IN K ▁OR A',
  '▁HE Y ▁S IN K ▁CO RA',
  '▁HE Y ▁S Y N ▁K OR A',
  '▁HE Y ▁S IN K ER ▁A',
];

/// The keyword list in the spotter's file format, with the boost and
/// threshold for [sensitivity] on every line.
String buildWakeKeywords(WakeSensitivity sensitivity) {
  return [
    for (final tokens in kWakeKeywordTokens)
      '$tokens :${sensitivity.score} #${sensitivity.threshold} @$kWakeLabel',
  ].join('\n');
}
