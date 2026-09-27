import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'screens/scanner_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(QuishGuardApp());
}

class QuishGuardApp extends StatelessWidget {
  QuishGuardApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'QuishGuard AI',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: const Color(0xFF0F172A),
        primaryColor: const Color(0xFF6366F1),
        textTheme: GoogleFonts.interTextTheme(
          ThemeData.dark().textTheme,
        ),
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFF6366F1),
          secondary: Color(0xFF22C55E),
          error: Color(0xFFEF4444),
        ),
      ),
      home: ScannerScreen(),
    );
  }
}