# Wake-word model

On-device keyword-spotting model used for "Hey Synkora".

- Model: `sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01` (int8 weights)
- Source: https://github.com/k2-fsa/sherpa-onnx/releases/tag/kws-models
- Architecture: streaming zipformer transducer (~3.3M parameters), BPE units,
  trained with icefall on GigaSpeech XL.
- License: Apache License 2.0

The model is general purpose; the wake phrase is defined by the keyword list in
`lib/src/voice/wake/wake_keywords.dart`, not by retraining. Audio is processed
entirely on the phone.
