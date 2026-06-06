import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class SynkoraColors {
  static const background = Color(0xFFF8FAFC);
  static const panel = Color(0xFFFFFFFF);
  static const surface = Color(0xFFEFF4F8);
  static const border = Color(0x180F172A);
  static const ink = Color(0xFF0F172A);
  static const muted = Color(0xFF64748B);
  static const primary = Color(0xFF79DFBC);
  static const primaryDeep = Color(0xFF145C4B);
  static const accentWarm = Color(0xFFF6C794);
  static const danger = Color(0xFFDC2626);
}

ThemeData buildSynkoraTheme() {
  final colorScheme = const ColorScheme.light(
    primary: SynkoraColors.primary,
    onPrimary: SynkoraColors.ink,
    secondary: SynkoraColors.accentWarm,
    onSecondary: SynkoraColors.ink,
    surface: SynkoraColors.panel,
    onSurface: SynkoraColors.ink,
    error: SynkoraColors.danger,
    onError: Colors.white,
  );

  final baseText = GoogleFonts.plusJakartaSansTextTheme();
  return ThemeData(
    useMaterial3: true,
    colorScheme: colorScheme,
    scaffoldBackgroundColor: SynkoraColors.background,
    textTheme: baseText.copyWith(
      displayLarge: GoogleFonts.spaceGrotesk(
        fontSize: 42,
        fontWeight: FontWeight.w700,
        color: SynkoraColors.ink,
      ),
      displayMedium: GoogleFonts.spaceGrotesk(
        fontSize: 32,
        fontWeight: FontWeight.w700,
        color: SynkoraColors.ink,
      ),
      headlineMedium: GoogleFonts.spaceGrotesk(
        fontSize: 24,
        fontWeight: FontWeight.w700,
        color: SynkoraColors.ink,
      ),
      titleLarge: GoogleFonts.spaceGrotesk(
        fontSize: 20,
        fontWeight: FontWeight.w700,
        color: SynkoraColors.ink,
      ),
      bodyLarge: baseText.bodyLarge?.copyWith(
        color: SynkoraColors.ink,
        height: 1.4,
      ),
      bodyMedium: baseText.bodyMedium?.copyWith(
        color: SynkoraColors.muted,
        height: 1.4,
      ),
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: Colors.transparent,
      foregroundColor: SynkoraColors.ink,
      elevation: 0,
      centerTitle: false,
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: SynkoraColors.panel,
      hintStyle: const TextStyle(color: SynkoraColors.muted),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(24),
        borderSide: const BorderSide(color: SynkoraColors.border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(24),
        borderSide: const BorderSide(color: SynkoraColors.border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(24),
        borderSide: const BorderSide(
          color: SynkoraColors.primaryDeep,
          width: 1.5,
        ),
      ),
      contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
    ),
    cardTheme: CardThemeData(
      color: SynkoraColors.panel,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(28),
        side: const BorderSide(color: SynkoraColors.border),
      ),
    ),
    snackBarTheme: SnackBarThemeData(
      backgroundColor: SynkoraColors.ink,
      contentTextStyle: baseText.bodyMedium?.copyWith(color: Colors.white),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
      behavior: SnackBarBehavior.floating,
    ),
    bottomNavigationBarTheme: const BottomNavigationBarThemeData(
      backgroundColor: SynkoraColors.panel,
      selectedItemColor: SynkoraColors.primaryDeep,
      unselectedItemColor: SynkoraColors.muted,
      type: BottomNavigationBarType.fixed,
      elevation: 8,
    ),
  );
}
