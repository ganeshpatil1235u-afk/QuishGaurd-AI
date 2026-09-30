import 'package:flutter/material.dart';
import 'screens/splash_screen.dart';
import 'screens/home_screen.dart';
import 'screens/scanner_screen.dart';
import 'theme/app_theme.dart';

void main() {
  runApp(const QuishGuardApp());
}

class QuishGuardApp extends StatelessWidget {
  const QuishGuardApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'QuishGuard AI',
      theme: AppTheme.darkTheme,
      debugShowCheckedModeBanner: false,
      home: const SplashScreen(),
      routes: {
        '/home': (context) => const HomeScreen(),
        '/scanner': (context) => ScannerScreen(),
      },
    );
  }
}