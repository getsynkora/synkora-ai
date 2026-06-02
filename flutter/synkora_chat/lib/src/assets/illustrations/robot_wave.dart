// SVG illustration: robot waving goodbye with checkmark — used on session ended screen.
const String robotWaveSvgTemplate = '''
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 180" fill="none">
  <!-- Shadow -->
  <ellipse cx="80" cy="172" rx="36" ry="6" fill="#000" fill-opacity="0.06"/>

  <!-- Legs -->
  <rect x="56" y="140" width="16" height="24" rx="8" fill="#PRIMARY"/>
  <rect x="88" y="140" width="16" height="24" rx="8" fill="#PRIMARY"/>
  <rect x="50" y="158" width="26" height="10" rx="5" fill="#PRIMARYDARK"/>
  <rect x="84" y="158" width="26" height="10" rx="5" fill="#PRIMARYDARK"/>

  <!-- Body -->
  <rect x="44" y="82" width="72" height="62" rx="18" fill="#PRIMARY"/>
  <rect x="56" y="96" width="48" height="30" rx="8" fill="white" fill-opacity="0.2"/>

  <!-- Checkmark on body -->
  <circle cx="80" cy="111" r="12" fill="white" fill-opacity="0.9"/>
  <polyline points="74,111 79,116 87,105"
    stroke="#22C55E" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>

  <!-- Neck -->
  <rect x="72" y="74" width="16" height="12" rx="4" fill="#PRIMARYDARK"/>

  <!-- Head -->
  <rect x="42" y="36" width="76" height="60" rx="22" fill="#PRIMARYLIGHT"/>
  <rect x="50" y="40" width="36" height="10" rx="5" fill="white" fill-opacity="0.25"/>

  <!-- Eyes — happy squint -->
  <path d="M64 62 Q70 57 76 62" stroke="#1E293B" stroke-width="2.5"
    stroke-linecap="round" fill="none"/>
  <path d="M84 62 Q90 57 96 62" stroke="#1E293B" stroke-width="2.5"
    stroke-linecap="round" fill="none"/>

  <!-- Big smile -->
  <path d="M66 74 Q80 86 94 74" stroke="#1E293B" stroke-width="2.5"
    stroke-linecap="round" fill="none"/>

  <!-- Antenna -->
  <rect x="77" y="20" width="6" height="18" rx="3" fill="#PRIMARYDARK"/>
  <circle cx="80" cy="16" r="7" fill="#PRIMARY"/>
  <circle cx="80" cy="16" r="3.5" fill="white"/>

  <!-- Left arm down -->
  <rect x="14" y="90" width="32" height="14" rx="7" fill="#PRIMARY"/>
  <circle cx="18" cy="97" r="9" fill="#PRIMARYLIGHT"/>

  <!-- Right arm raised/waving -->
  <rect x="116" y="72" width="30" height="14" rx="7"
    fill="#PRIMARY" transform="rotate(-35 116 72)"/>
  <circle cx="144" cy="62" r="9" fill="#PRIMARYLIGHT"/>

  <!-- Wave lines from right hand -->
  <path d="M150 50 Q156 44 150 38" stroke="#PRIMARY" stroke-width="2"
    stroke-linecap="round" fill="none" opacity="0.6"/>
  <path d="M155 54 Q163 47 156 39" stroke="#PRIMARY" stroke-width="1.5"
    stroke-linecap="round" fill="none" opacity="0.4"/>
</svg>
''';

String robotWaveSvg(String primaryHex) {
  final dark = _darken(primaryHex);
  final light = _lighten(primaryHex);
  return robotWaveSvgTemplate
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
