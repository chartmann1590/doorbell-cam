import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:doorbellcam_app/main.dart';

void main() {
  testWidgets('connect gate renders and starts discovery', (tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(const DoorbellApp());
    await tester.pump();
    expect(find.textContaining('DoorbellCam hub'), findsOneWidget);
  });
}
