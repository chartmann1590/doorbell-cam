import 'package:flutter_local_notifications/flutter_local_notifications.dart';

/// Foreground/local notifications for hub alerts.
class Notify {
  static final _plugin = FlutterLocalNotificationsPlugin();

  static Future<void> init() async {
    const android = AndroidInitializationSettings('@mipmap/ic_launcher');
    const settings = InitializationSettings(android: android);
    await _plugin.initialize(settings);
    final impl = _plugin.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>();
    // Android 13+ needs the permission granted at runtime.
    await impl?.requestNotificationsPermission();
  }

  static Future<void> showAlert({required String title, required String body}) async {
    const details = NotificationDetails(
      android: AndroidNotificationDetails(
        'doorbell_alerts',
        'Doorbell alerts',
        channelDescription: 'Person and face detections from your DoorbellCam hub',
        importance: Importance.max,
        priority: Priority.high,
        showWhen: true,
      ),
    );
    await _plugin.show(DateTime.now().millisecondsSinceEpoch % 100000, title, body, details);
  }
}
