// SVG illustration: robot with floating chat bubble — used on empty chat state.
// The robot body uses #PRIMARY which is replaced at runtime with primaryColor hex.
const String robotChatSvgTemplate = '''
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 220" fill="none">
  <!-- Shadow -->
  <ellipse cx="100" cy="210" rx="45" ry="8" fill="#000" fill-opacity="0.06"/>

  <!-- Robot legs -->
  <rect x="72" y="168" width="18" height="28" rx="9" fill="#PRIMARY"/>
  <rect x="110" y="168" width="18" height="28" rx="9" fill="#PRIMARY"/>

  <!-- Robot feet -->
  <rect x="66" y="190" width="28" height="12" rx="6" fill="#PRIMARYDARK"/>
  <rect x="104" y="190" width="28" height="12" rx="6" fill="#PRIMARYDARK"/>

  <!-- Robot body -->
  <rect x="58" y="100" width="84" height="72" rx="20" fill="#PRIMARY"/>

  <!-- Body panel -->
  <rect x="72" y="116" width="56" height="36" rx="10" fill="white" fill-opacity="0.2"/>

  <!-- Heart / pulse line on body -->
  <polyline points="76,134 82,134 86,124 90,144 94,128 98,134 110,134 116,134 120,134"
    stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>

  <!-- Robot neck -->
  <rect x="90" y="90" width="20" height="14" rx="4" fill="#PRIMARYDARK"/>

  <!-- Robot head -->
  <rect x="56" y="48" width="88" height="66" rx="24" fill="#PRIMARYLIGHT"/>

  <!-- Head highlight -->
  <rect x="64" y="52" width="40" height="12" rx="6" fill="white" fill-opacity="0.25"/>

  <!-- Eyes -->
  <circle cx="83" cy="74" r="10" fill="white"/>
  <circle cx="117" cy="74" r="10" fill="white"/>
  <circle cx="85" cy="75" r="5" fill="#1E293B"/>
  <circle cx="119" cy="75" r="5" fill="#1E293B"/>
  <!-- Eye shine -->
  <circle cx="87" cy="73" r="2" fill="white"/>
  <circle cx="121" cy="73" r="2" fill="white"/>

  <!-- Smile -->
  <path d="M87 88 Q100 97 113 88" stroke="#1E293B" stroke-width="2.5"
    stroke-linecap="round" fill="none"/>

  <!-- Antenna -->
  <rect x="97" y="30" width="6" height="20" rx="3" fill="#PRIMARYDARK"/>
  <circle cx="100" cy="26" r="8" fill="#PRIMARY"/>
  <circle cx="100" cy="26" r="4" fill="white"/>

  <!-- Arms -->
  <rect x="24" y="108" width="36" height="16" rx="8" fill="#PRIMARY"/>
  <rect x="140" y="108" width="36" height="16" rx="8" fill="#PRIMARY"/>

  <!-- Left hand open -->
  <circle cx="28" cy="116" r="10" fill="#PRIMARYLIGHT"/>
  <!-- Right hand waving gesture -->
  <circle cx="172" cy="116" r="10" fill="#PRIMARYLIGHT"/>

  <!-- Chat bubble 1 (top right, floating) -->
  <rect x="124" y="4" width="72" height="32" rx="14" fill="white"
    stroke="#E2E8F0" stroke-width="1.5"/>
  <path d="M138 36 L130 46 L148 36" fill="white" stroke="#E2E8F0"
    stroke-width="1.5" stroke-linejoin="round"/>
  <rect x="134" y="14" width="40" height="5" rx="2.5" fill="#CBD5E1"/>
  <rect x="134" y="23" width="28" height="5" rx="2.5" fill="#E2E8F0"/>

  <!-- Chat bubble 2 (left, smaller) -->
  <rect x="4" y="20" width="54" height="26" rx="12" fill="#F1F5F9"
    stroke="#E2E8F0" stroke-width="1.5"/>
  <path d="M46 46 L54 54 L36 46" fill="#F1F5F9" stroke="#E2E8F0"
    stroke-width="1.5" stroke-linejoin="round"/>
  <rect x="12" y="28" width="30" height="4" rx="2" fill="#CBD5E1"/>
  <rect x="12" y="36" width="20" height="4" rx="2" fill="#E2E8F0"/>
</svg>
''';

String robotChatSvg(String primaryHex) {
  final dark = _darken(primaryHex);
  final light = _lighten(primaryHex);
  return robotChatSvgTemplate
      .replaceAll('#PRIMARY', primaryHex)
      .replaceAll('#PRIMARYDARK', dark)
      .replaceAll('#PRIMARYLIGHT', light);
}

String _darken(String hex) {
  final c = _parseHex(hex);
  return _toHex(
    (c[0] * 0.75).round().clamp(0, 255),
    (c[1] * 0.75).round().clamp(0, 255),
    (c[2] * 0.75).round().clamp(0, 255),
  );
}

String _lighten(String hex) {
  final c = _parseHex(hex);
  return _toHex(
    (c[0] + (255 - c[0]) * 0.35).round().clamp(0, 255),
    (c[1] + (255 - c[1]) * 0.35).round().clamp(0, 255),
    (c[2] + (255 - c[2]) * 0.35).round().clamp(0, 255),
  );
}

List<int> _parseHex(String hex) {
  final h = hex.replaceAll('#', '');
  return [
    int.parse(h.substring(0, 2), radix: 16),
    int.parse(h.substring(2, 4), radix: 16),
    int.parse(h.substring(4, 6), radix: 16),
  ];
}

String _toHex(int r, int g, int b) =>
    '#${r.toRadixString(16).padLeft(2, '0')}'
    '${g.toRadixString(16).padLeft(2, '0')}'
    '${b.toRadixString(16).padLeft(2, '0')}';
