import 'dart:async';
import 'package:flutter/material.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c;
  late final Animation<double> _fade;
  late final Animation<double> _scale;
  late final Animation<double> _glow;

  @override
  void initState() {
    super.initState();

    _c = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1300),
    );

    _fade = CurvedAnimation(parent: _c, curve: Curves.easeOutCubic);
    _scale = Tween<double>(begin: 0.92, end: 1.0).animate(
      CurvedAnimation(parent: _c, curve: Curves.easeOutCubic),
    );
    _glow = Tween<double>(begin: 0.25, end: 0.55).animate(
      CurvedAnimation(parent: _c, curve: Curves.easeInOut),
    );

    _c.forward();

    Timer(const Duration(milliseconds: 1600), () {
      if (!mounted) return;
      Navigator.of(context).pushReplacementNamed('/home');
    });
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      // Premium dark background (even if the app uses light theme)
      body: AnimatedBuilder(
        animation: _c,
        builder: (_, __) {
          return Container(
            decoration: const BoxDecoration(
              gradient: RadialGradient(
                center: Alignment(0.0, -0.25),
                radius: 1.1,
                colors: [
                  Color(0xFF0B1220), // deep navy
                  Color(0xFF050A14), // near black
                ],
              ),
            ),
            child: SafeArea(
              child: Center(
                child: Opacity(
                  opacity: _fade.value,
                  child: Transform.scale(
                    scale: _scale.value,
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        // Glow + logo
                        Container(
                          padding: const EdgeInsets.all(18),
                         decoration: BoxDecoration(
  borderRadius: BorderRadius.circular(28),
  color: Colors.white.withOpacity(0.04),
  boxShadow: [
    BoxShadow(
      color: const Color(0xFF6366F1).withOpacity(_glow.value),
      blurRadius: 34,
      spreadRadius: 2,
    ),
  ],
),
                          child: Image.asset(
                            'assets/images/logo.png',
                            width: 180,
                            height: 180,
                            fit: BoxFit.contain,
                          ),
                        ),

                        const SizedBox(height: 18),

                        const Text(
                          'QuishGuard AI',
                          style: TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.w700,
                            color: Colors.white,
                            letterSpacing: 0.2,
                          ),
                        ),
                        const SizedBox(height: 6),
                        const Text(
                          'Scan → AI Analysis → Threat Detection → Protection',
                          style: TextStyle(
                            fontSize: 12,
                            color: Colors.white70,
                          ),
                          textAlign: TextAlign.center,
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}