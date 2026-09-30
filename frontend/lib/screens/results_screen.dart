import 'dart:io' show Platform;
import 'package:android_intent_plus/android_intent.dart';
import 'package:android_intent_plus/flag.dart';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

class ResultsScreen extends StatefulWidget {
  final Map<String, dynamic> result;

  const ResultsScreen({Key? key, required this.result}) : super(key: key);

  @override
  State<ResultsScreen> createState() => _ResultsScreenState();
}

class _ResultsScreenState extends State<ResultsScreen> {
  Map<String, dynamic> get result => widget.result;

  bool _launching = false;

  String get _payload => (result["decoded_payload"] ?? "").toString();
  String get _level => (result["risk_level"] ?? "UNKNOWN").toString();

  Map get _targetApp => (result["target_app"] as Map?) ?? {};
  String get _targetCategory => (_targetApp["category"] ?? "text").toString();
  String get _targetLabel => (_targetApp["label"] ?? "App").toString();
  bool get _isPayment => _targetCategory == "payment";

  // Backend decides these — the app just obeys.
  bool get _canAutoOpen => result["auto_open_allowed"] == true;
  bool get _canManualOpen => result["manual_open_allowed"] == true;

  /// Opens the right app for this QR.
  ///
  /// Payment QRs (upi://): always shows the Android app chooser, so the user
  /// picks from whichever UPI apps are installed on THIS phone (PhonePe,
  /// Google Pay, Paytm, etc.) rather than being sent to one hardcoded app.
  ///
  /// Everything else (WhatsApp, Telegram, forms, browser links, email, tel,
  /// sms...): opened the normal Android way, which already routes to the
  /// matching installed app when one is registered for that link.
  Future<void> _openTargetApp() async {
    if (_launching) return;
    _launching = true;

    try {
      if (_isPayment) {
        await _openPaymentChooser();
      } else {
        await _openGenericLink();
      }
    } finally {
      _launching = false;
    }
  }

  Future<void> _openPaymentChooser() async {
    final payload = _payload.trim();

    if (!payload.toLowerCase().startsWith("upi://")) {
      _toast("Not a UPI payment QR");
      return;
    }

    // 1) Force the system app chooser so the user picks which payment app
    //    to use, even if one app is set as the phone's default handler.
    if (Platform.isAndroid) {
      try {
        final intent = AndroidIntent(
          action: 'action_view',
          data: payload,
        );
        await intent.launchChooser('Pay with');
        return;
      } catch (e) {
        // fall through to the generic launch below
      }
    }

    // 2) Fallback: generic upi:// launch (shows the chooser on most phones
    //    if no default payment app is set).
    try {
      final ok = await launchUrl(
        Uri.parse(payload),
        mode: LaunchMode.externalApplication,
      );
      if (ok) return;
    } catch (_) {}

    _toast(
      "Could not open a payment app.\n"
      "Make sure at least one UPI app (PhonePe, Google Pay, Paytm, etc.) "
      "is installed.",
      seconds: 8,
    );
  }

  Future<void> _openGenericLink() async {
    String link = _payload.trim();
    final category = _targetCategory;

    // mailto:, tel:, sms: already carry their own scheme — leave them as is.
    // Everything web-like gets an https:// prefix if it's missing one.
    final needsHttpPrefix = [
      "whatsapp", "telegram", "instagram", "facebook", "form", "maps",
      "youtube", "linkedin", "playstore", "browser",
    ];
    if (needsHttpPrefix.contains(category) && !link.toLowerCase().startsWith("http")) {
      link = "https://$link";
    }

    final uri = Uri.tryParse(link);
    if (uri == null) {
      _toast("Could not open this link");
      return;
    }

    try {
      final ok = await launchUrl(uri, mode: LaunchMode.externalApplication);
      if (!ok) {
        _toast("Could not open $_targetLabel. Is the app installed?");
      }
    } catch (e) {
      _toast("Failed to open: $e");
    }
  }

  void _toast(String msg, {int seconds = 4}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg),
        backgroundColor: const Color(0xFFEF4444),
        duration: Duration(seconds: seconds),
      ),
    );
  }

  IconData _targetIcon(String category) {
    switch (category) {
      case "payment": return Icons.account_balance_wallet;
      case "whatsapp": return Icons.chat;
      case "telegram": return Icons.send;
      case "instagram": return Icons.camera_alt;
      case "facebook": return Icons.thumb_up;
      case "form": return Icons.description;
      case "maps": return Icons.location_on;
      case "youtube": return Icons.play_circle_fill;
      case "linkedin": return Icons.work;
      case "playstore": return Icons.shop;
      case "email": return Icons.email;
      case "phone": return Icons.call;
      case "sms": return Icons.sms;
      default: return Icons.open_in_new;
    }
  }

  // Tap-only: nothing opens automatically. SAFE shows a normal action
  // button; MEDIUM shows an explicit "anyway, at your risk" button;
  // HIGH/CRITICAL shows nothing (blocked by the backend flags).
  Widget _openSection(Color color) {
    const paymentPurple = Color(0xFF5F259F);
    final buttonColor = _isPayment ? paymentPurple : const Color(0xFF6366F1);

    if (_canAutoOpen) {
      return Column(
        children: [
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: _openTargetApp,
              icon: Icon(_targetIcon(_targetCategory)),
              label: Text(
                _isPayment ? "Choose Payment App" : "Open in $_targetLabel",
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
              ),
              style: ElevatedButton.styleFrom(
                backgroundColor: buttonColor,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
            ),
          ),
          const SizedBox(height: 8),
        ],
      );
    }

    // MEDIUM: allow an explicit, deliberate override. HIGH/CRITICAL: blocked.
    if (_canManualOpen) {
      return Column(
        children: [
          SizedBox(
            width: double.infinity,
            child: OutlinedButton(
              onPressed: _openTargetApp,
              style: OutlinedButton.styleFrom(
                foregroundColor: color,
                side: BorderSide(color: color),
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              child: Text(
                _isPayment
                    ? "Proceed to payment anyway (at your risk)"
                    : "Open in $_targetLabel anyway (at your risk)",
              ),
            ),
          ),
          const SizedBox(height: 8),
        ],
      );
    }
    return const SizedBox.shrink();
  }

  Color _riskColor(String level) {
    switch (level) {
      case "CRITICAL": return const Color(0xFFEF4444);
      case "HIGH":     return const Color(0xFFF97316);
      case "MEDIUM":   return const Color(0xFFEAB308);
      default:         return const Color(0xFF22C55E);
    }
  }

  String _riskIcon(String level) {
    switch (level) {
      case "CRITICAL": return "🚨";
      case "HIGH":     return "⚠️";
      case "MEDIUM":   return "⚡";
      default:         return "✅";
    }
  }

  @override
  Widget build(BuildContext context) {
    final score       = (result["threat_score"] as num?)?.toDouble() ?? 0;
    final level       = (result["risk_level"] ?? "UNKNOWN").toString();
    final verdict     = (result["verdict"] ?? "").toString();
    final payload     = (result["decoded_payload"] ?? "").toString();
    final payloadType = (result["payload_type"] ?? "").toString();
    final recommendation = (result["recommendation"] ?? "").toString();
    final color       = _riskColor(level);
    final icon        = _riskIcon(level);

    final analysis = (result["analysis"] as Map?) ?? {};
    final upi   = analysis["upi_analysis"]  as Map? ?? {};
    final hf    = analysis["huggingface_ai"] as Map? ?? {};
    final whois = analysis["whois_api"]      as Map? ?? {};
    final vt    = analysis["virustotal_api"] as Map? ?? {};

    return Scaffold(
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        title: const Text(
          "🛡️ Threat Report",
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [

            // Score Circle
            Container(
              width: 150,
              height: 150,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                border: Border.all(color: color, width: 4),
                color: color.withOpacity(0.08),
              ),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(icon, style: const TextStyle(fontSize: 32)),
                  Text(
                    score.toStringAsFixed(1),
                    style: TextStyle(
                      fontSize: 36,
                      fontWeight: FontWeight.bold,
                      color: color,
                    ),
                  ),
                  const Text(
                    "/ 100",
                    style: TextStyle(fontSize: 12, color: Colors.white54),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),

            // Level
            Text(
              level,
              style: TextStyle(
                fontSize: 28,
                fontWeight: FontWeight.bold,
                color: color,
              ),
            ),
            const SizedBox(height: 8),

            // Badge (payload type + which app this QR belongs to)
            Wrap(
              spacing: 8,
              alignment: WrapAlignment.center,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.white10,
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    payloadType,
                    style: const TextStyle(fontSize: 12, color: Colors.white54),
                  ),
                ),
                if (_targetCategory != "text")
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                    decoration: BoxDecoration(
                      color: const Color(0xFF6366F1).withOpacity(0.15),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: const Color(0xFF6366F1).withOpacity(0.4)),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(_targetIcon(_targetCategory), size: 12, color: const Color(0xFFC7D2FE)),
                        const SizedBox(width: 4),
                        Text(
                          _targetLabel,
                          style: const TextStyle(fontSize: 12, color: Color(0xFFC7D2FE)),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 16),

            // Open-in-app button first, so it is visible without scrolling
            _openSection(color),

            _card("Verdict", verdict, borderColor: color, textColor: color),
            const SizedBox(height: 8),
            _card("Recommendation", recommendation),
            const SizedBox(height: 8),
            _card("Decoded Payload", payload),
            const SizedBox(height: 8),

            // UPI
            if (upi["is_upi"] == true) ...[
              _card(
                "💳 UPI Analysis",
                "VPA: ${upi["payee_vpa"] ?? "Unknown"}\n"
                "Payee: ${upi["payee_name"] ?? "Unknown"}\n"
                "Amount: Rs.${upi["amount"] ?? 0}\n"
                "Action: ${upi["actual_action"] ?? "DEBIT"}\n"
                "Risk Score: ${upi["upi_risk_score"] ?? 0}/100",
              ),
              const SizedBox(height: 8),
              if ((upi["risks"] as List?)?.isNotEmpty == true)
                ...((upi["risks"] as List).map((r) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: _card(
                    "⚠️ ${r["severity"]}: ${r["type"]}",
                    r["detail"] ?? "",
                    borderColor: const Color(0xFFEF4444),
                    textColor: const Color(0xFFEF4444),
                  ),
                ))),
            ],

            // HF
            if (hf.isNotEmpty && hf["model"] != "skipped") ...[
              _card(
                "🧠 AI Analysis",
                "Model: ${hf["model"] ?? "Heuristic"}\n"
                "Phishing: ${(((hf["phishing_probability"] ?? 0) as num) * 100).toStringAsFixed(1)}%\n"
                "Is Phishing: ${hf["is_phishing"] ?? false}",
              ),
              const SizedBox(height: 8),
            ],

            // WHOIS
            if (whois.isNotEmpty && whois["domain"] != null) ...[
              _card(
                "🌐 WHOIS",
                "Domain: ${whois["domain"]}\n"
                "Age: ${whois["age_days"]} days\n"
                "Zero-Day: ${whois["is_zero_day"]}\n"
                "Risk: ${whois["risk_score"]}",
              ),
              const SizedBox(height: 8),
            ],

            // VT
            if (vt.isNotEmpty && vt["service"] != "skipped") ...[
              _card(
                "🦠 VirusTotal",
                "Malicious: ${vt["malicious_votes"] ?? 0}\n"
                "Flagged: ${vt["flagged"] ?? false}\n"
                "Score: ${vt["threat_score"] ?? 0}",
              ),
              const SizedBox(height: 8),
            ],

            _card(
              "🔧 Debug",
              "Backend engine: ${result["engine_version"] ?? "OLD BACKEND"}\n"
              "Risk level: $level\n"
              "Target app: $_targetCategory ($_targetLabel)\n"
              "auto_open_allowed: ${result["auto_open_allowed"]}\n"
              "manual_open_allowed: ${result["manual_open_allowed"]}",
            ),
            const SizedBox(height: 12),

            // Scan Again Button
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () => Navigator.pop(context),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF6366F1),
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: const Text(
                  "Scan Another",
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 15,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }

  Widget _card(
    String title,
    String body, {
    Color? borderColor,
    Color? textColor,
  }) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.05),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: borderColor ?? Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(
              color: Color(0xFF6366F1),
              fontWeight: FontWeight.bold,
              fontSize: 13,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            body,
            style: TextStyle(
              color: textColor ?? Colors.white70,
              fontSize: 12,
              height: 1.6,
            ),
          ),
        ],
      ),
    );
  }
}