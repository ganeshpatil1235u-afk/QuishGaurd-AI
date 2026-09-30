import 'package:flutter_test/flutter_test.dart';
import 'package:quishguard_frontend/main.dart';

void main() {
  testWidgets('App builds smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(const QuishGuardApp());
    await tester.pump(); // allow first frame
    expect(find.text('QuishGuard AI'), findsWidgets);
  });
}