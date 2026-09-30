import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:permission_handler/permission_handler.dart';
import 'results_screen.dart';
import 'home_screen.dart';

class ScannerScreen extends StatefulWidget {
  ScannerScreen({Key? key}) : super(key: key);

  @override
  State<ScannerScreen> createState() => _ScannerScreenState();
}

class _ScannerScreenState extends State<ScannerScreen>
    with WidgetsBindingObserver {
  // Controllers
  final MobileScannerController cameraController = MobileScannerController(
    facing: CameraFacing.back,
    torchEnabled: false,
    formats: const [BarcodeFormat.qrCode],
    detectionSpeed: DetectionSpeed.noDuplicates,
  );
  final _contextCtrl = TextEditingController();

  // State
  bool _loading = false;
  bool _cameraActive = true;
  bool _hasPermission = false;
  bool _scanned = false;
  String _backendStatus = "Checking...";
  Color _statusColor = Colors.grey;
  double _zoom = 0.0; // 0.0 = no zoom, 1.0 = max zoom
  double _zoomAtPinchStart = 0.0;

  // API URL
  //
  // Option A: edit the default value below.
  // Option B: run Flutter with:
  // flutter run --dart-define=BACKEND_URL=http://YOUR_LAN_IP:8000
  //
  // For Android emulator only, you may use:
  // http://10.0.2.2:8000
  //
  // For a real phone, use your laptop LAN IP, example:
  // http://192.168.1.20:8000
  static const String backendBaseUrl = String.fromEnvironment(
    'BACKEND_URL',
    defaultValue: 'http://192.168.1.20:8000',
  );

  // /api/v2/* routes only exist in the UPDATED backend. An old backend returns
  // 404 here, so the app can never silently use old scoring logic.
  static String get apiUrl => '$backendBaseUrl/api/v2/scan';
  static String get healthUrl => '$backendBaseUrl/api/v2/health';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _requestCameraPermission();
    _checkBackend();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    cameraController.dispose();
    _contextCtrl.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // Only touch the camera when we own it: permission granted, not mid-scan.
    if (!_hasPermission || _scanned) return;
    if (state == AppLifecycleState.resumed) {
      _safeStart();
    } else if (state == AppLifecycleState.paused) {
      _safeStop();
    }
  }

  // start()/stop() throw if the camera is already in that state. Swallow it.
  Future<void> _safeStart() async {
    try {
      await cameraController.start();
    } catch (_) {}
  }

  Future<void> _safeStop() async {
    try {
      await cameraController.stop();
    } catch (_) {}
  }

  // Request camera permission
  Future<void> _requestCameraPermission() async {
    final status = await Permission.camera.request();
    if (!mounted) return;
    setState(() {
      _hasPermission = status.isGranted;
    });

    if (!status.isGranted) {
      _showMessage(
        "Camera permission needed to scan QR codes",
        isError: true,
      );
    }
  }

  // Check backend health (uses /api/v2/health: an OLD backend has no such route)
  Future<void> _checkBackend() async {
    try {
      final res = await http
          .get(Uri.parse(healthUrl))
          .timeout(const Duration(seconds: 5));

      if (!mounted) return;
      if (res.statusCode == 200) {
        String v = "";
        try {
          v = (jsonDecode(res.body)["version"] ?? "").toString();
        } catch (_) {}
        setState(() {
          _backendStatus = v.isEmpty ? "✅ Online" : "✅ Online v$v";
          _statusColor = const Color(0xFF22C55E);
        });
      } else if (res.statusCode == 404) {
        setState(() {
          _backendStatus = "⚠️ OLD backend";
          _statusColor = const Color(0xFFEAB308);
        });
      } else {
        throw Exception();
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _backendStatus = "❌ Offline";
        _statusColor = const Color(0xFFEF4444);
      });
    }
  }

  // Called when QR code is detected by camera
  void _onQRDetected(BarcodeCapture capture) async {
    if (_scanned || _loading) return;

    final barcode = capture.barcodes.first;
    final qrData = barcode.rawValue;

    if (qrData == null || qrData.isEmpty) return;

    HapticFeedback.heavyImpact();

    setState(() {
      _scanned = true;
      _cameraActive = false;
    });

    await _safeStop();

    if (!mounted) return;
    _showQRConfirmDialog(qrData);
  }

  // Show confirmation dialog before scanning
  void _showQRConfirmDialog(String qrData) {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF1E293B),
        title: const Text(
          "🔍 QR Detected!",
          style: TextStyle(color: Colors.white),
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              "Detected payload:",
              style: TextStyle(
                color: Colors.white54,
                fontSize: 12,
              ),
            ),
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Colors.black26,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                qrData.length > 100
                    ? "${qrData.substring(0, 100)}..."
                    : qrData,
                style: const TextStyle(
                  color: Colors.white70,
                  fontSize: 12,
                ),
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _contextCtrl,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 13,
              ),
              decoration: InputDecoration(
                hintText: "Sign text? e.g. Scan to RECEIVE Rs.5000",
                hintStyle: const TextStyle(
                  color: Colors.white30,
                  fontSize: 12,
                ),
                filled: true,
                fillColor: Colors.black26,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                  borderSide: BorderSide.none,
                ),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.pop(ctx);
              _resetScanner();
            },
            child: const Text(
              "Cancel",
              style: TextStyle(color: Colors.white54),
            ),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(ctx);
              _analyzePayload(qrData);
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF6366F1),
              foregroundColor: Colors.white,
            ),
            child: const Text(
              "Analyze Threat",
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
          ),
        ],
      ),
    );
  }

  // Send payload to backend for analysis
  Future<void> _analyzePayload(String payload) async {
    setState(() => _loading = true);

    try {
      final contextText = _contextCtrl.text.trim();

      final res = await http
          .post(
            Uri.parse(apiUrl),
            headers: {"Content-Type": "application/json"},
            body: jsonEncode({
              "qr_decoded_text": payload,
              "context_text": contextText.isEmpty ? null : contextText,
              "scan_source": "flutter_mobile_camera",
            }),
          )
          .timeout(const Duration(seconds: 45));

      if (res.statusCode == 200) {
        final data = jsonDecode(res.body) as Map<String, dynamic>;

        if (!mounted) return;

        // Record scan stats
final level = (data["risk_level"] ?? "").toString();
final isThreat = level == "HIGH" || level == "CRITICAL" || level == "MEDIUM";
ScanStats.recordScan(isThreat: isThreat);

await Navigator.push(
  context,
  MaterialPageRoute(
    builder: (_) => ResultsScreen(result: data),
  ),
);

_resetScanner();
      } else if (res.statusCode == 404) {
        _showMessage(
          "OLD backend detected (no /api/v2/scan).\n"
          "Stop the old server and start backend/main.py again.",
          isError: true,
        );
        _resetScanner();
      } else {
        _showMessage(
          "Server error: ${res.statusCode}",
          isError: true,
        );
        _resetScanner();
      }
    } catch (e) {
      _showMessage(
        "Cannot reach backend!\n"
        "Check your WiFi and backend IP address.",
        isError: true,
      );
      _resetScanner();
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  // Reset scanner to scan again
  void _resetScanner() {
    if (!mounted) return;
    setState(() {
      _scanned = false;
      _cameraActive = true;
    });

    _contextCtrl.clear();

    if (_hasPermission) {
      _safeStart();
    }
  }

  void _showMessage(String msg, {bool isError = false}) {
    if (!mounted) return;

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg),
        backgroundColor: isError
            ? const Color(0xFFEF4444)
            : const Color(0xFF22C55E),
        duration: const Duration(seconds: 4),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F172A),
      body: SafeArea(
        child: Column(
          children: [
            // Header
            Container(
              padding: const EdgeInsets.symmetric(
                horizontal: 20,
                vertical: 16,
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    "🛡️ QuishGuard AI",
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                  ),
                  GestureDetector(
                    onTap: _checkBackend,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 10,
                        vertical: 4,
                      ),
                      decoration: BoxDecoration(
                        color: _statusColor.withOpacity(0.15),
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(
                          color: _statusColor.withOpacity(0.5),
                        ),
                      ),
                      child: Text(
                        _backendStatus,
                        style: TextStyle(
                          color: _statusColor,
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),

            // Camera Viewfinder
            Expanded(
              flex: 5,
              child: Container(
                margin: const EdgeInsets.symmetric(
                  horizontal: 20,
                ),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(
                    color: const Color(0xFF6366F1),
                    width: 2,
                  ),
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(22),
                  child: _hasPermission
                      ? GestureDetector(
                      onScaleStart: (_) => _zoomAtPinchStart = _zoom,
                      onScaleUpdate: (details) async {
                        // details.scale: 1.0 = no change, >1 = pinch out (zoom in),
                        // <1 = pinch in (zoom out).
                        final delta = (details.scale - 1.0) * 0.8;
                        final newZoom =
                            (_zoomAtPinchStart + delta).clamp(0.0, 1.0);
                        if ((newZoom - _zoom).abs() < 0.01) return;
                        setState(() => _zoom = newZoom);
                        try {
                          await cameraController.setZoomScale(newZoom);
                        } catch (_) {}
                      },
                      child: Stack(
                          children: [
                            MobileScanner(
                              controller: cameraController,
                              onDetect: _onQRDetected,
                              fit: BoxFit.cover,
                              placeholderBuilder: (context, child) =>
                                  const Center(
                                child: CircularProgressIndicator(
                                  color: Color(0xFF6366F1),
                                ),
                              ),
                              errorBuilder: (context, error, child) =>
                                  _buildCameraError(error),
                            ),
                            _buildScanOverlay(),
                            if (_loading)
                              Container(
                                color: Colors.black54,
                                child: const Center(
                                  child: Column(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      CircularProgressIndicator(
                                        color: Color(0xFF6366F1),
                                      ),
                                      SizedBox(height: 16),
                                      Text(
                                        "Analyzing threat...",
                                        style: TextStyle(
                                          color: Colors.white,
                                          fontSize: 16,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                          ],
                        ),
                    )
                      : _buildPermissionDenied(),
                ),
              ),
            ),

            // Bottom Panel
            Expanded(
              flex: 2,
              child: Container(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    const Text(
                      "Point camera at a QR code",
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 4),
                    const Text(
                      "AI will check for UPI scams and phishing",
                      style: TextStyle(
                        color: Colors.white54,
                        fontSize: 12,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      "Server: $backendBaseUrl",
                      style: const TextStyle(
                        color: Colors.white24,
                        fontSize: 10,
                      ),
                    ),
                    const SizedBox(height: 8),
                    _buildZoomSlider(),
                    const SizedBox(height: 4),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                      children: [
                        _buildControlBtn(
                          icon: Icons.flash_on,
                          label: "Flash",
                          onTap: () async {
                            try {
                              await cameraController.toggleTorch();
                            } catch (_) {}
                          },
                        ),
                        _buildControlBtn(
                          icon: Icons.flip_camera_ios,
                          label: "Flip",
                          onTap: () async {
                            try {
                              await cameraController.switchCamera();
                            } catch (_) {}
                          },
                        ),
                        _buildControlBtn(
                          icon: Icons.wifi,
                          label: "Status",
                          onTap: _checkBackend,
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildScanOverlay() {
    return Center(
      child: Container(
        width: 220,
        height: 220,
        decoration: BoxDecoration(
          border: Border.all(
            color: const Color(0xFF6366F1),
            width: 3,
          ),
          borderRadius: BorderRadius.circular(16),
        ),
        child: Stack(
          children: [
            Positioned(
              top: 0,
              left: 0,
              child: _cornerMark(topLeft: true),
            ),
            Positioned(
              top: 0,
              right: 0,
              child: _cornerMark(topRight: true),
            ),
            Positioned(
              bottom: 0,
              left: 0,
              child: _cornerMark(bottomLeft: true),
            ),
            Positioned(
              bottom: 0,
              right: 0,
              child: _cornerMark(bottomRight: true),
            ),
          ],
        ),
      ),
    );
  }

  Widget _cornerMark({
    bool topLeft = false,
    bool topRight = false,
    bool bottomLeft = false,
    bool bottomRight = false,
  }) {
    return Container(
      width: 30,
      height: 30,
      decoration: BoxDecoration(
        border: Border(
          top: topLeft || topRight
              ? const BorderSide(
                  color: Color(0xFF22C55E),
                  width: 4,
                )
              : BorderSide.none,
          bottom: bottomLeft || bottomRight
              ? const BorderSide(
                  color: Color(0xFF22C55E),
                  width: 4,
                )
              : BorderSide.none,
          left: topLeft || bottomLeft
              ? const BorderSide(
                  color: Color(0xFF22C55E),
                  width: 4,
                )
              : BorderSide.none,
          right: topRight || bottomRight
              ? const BorderSide(
                  color: Color(0xFF22C55E),
                  width: 4,
                )
              : BorderSide.none,
        ),
      ),
    );
  }

  Widget _buildZoomSlider() {
    return Row(
      children: [
        const Icon(Icons.zoom_out, color: Colors.white38, size: 18),
        Expanded(
          child: SliderTheme(
            data: SliderTheme.of(context).copyWith(
              trackHeight: 3,
              thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 7),
              overlayShape: const RoundSliderOverlayShape(overlayRadius: 14),
            ),
            child: Slider(
              value: _zoom,
              min: 0.0,
              max: 1.0,
              activeColor: const Color(0xFF6366F1),
              inactiveColor: Colors.white12,
              onChanged: (v) async {
                setState(() => _zoom = v);
                try {
                  await cameraController.setZoomScale(v);
                } catch (_) {}
              },
            ),
          ),
        ),
        const Icon(Icons.zoom_in, color: Colors.white38, size: 18),
      ],
    );
  }

  Widget _buildControlBtn({
    required IconData icon,
    required String label,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.08),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: Colors.white12),
            ),
            child: Icon(
              icon,
              color: Colors.white70,
              size: 24,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            label,
            style: const TextStyle(
              color: Colors.white38,
              fontSize: 11,
            ),
          ),
        ],
      ),
    );
  }

  // Shows the real camera error instead of a silent black box
  Widget _buildCameraError(Object error) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.videocam_off, size: 56, color: Colors.white30),
            const SizedBox(height: 12),
            const Text(
              "Camera failed to start",
              style: TextStyle(
                color: Colors.white,
                fontSize: 16,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              error.toString(),
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.white54, fontSize: 12),
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _safeStart,
              child: const Text("Retry"),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPermissionDenied() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(
            Icons.camera_alt_outlined,
            size: 64,
            color: Colors.white30,
          ),
          const SizedBox(height: 16),
          const Text(
            "Camera Permission Required",
            style: TextStyle(
              color: Colors.white,
              fontSize: 16,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            "Please allow camera access\nto scan QR codes",
            style: TextStyle(
              color: Colors.white54,
              fontSize: 13,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 20),
          ElevatedButton(
            onPressed: () {
              openAppSettings();
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF6366F1),
              foregroundColor: Colors.white,
            ),
            child: const Text("Open Settings"),
          ),
        ],
      ),
    );
  }
}