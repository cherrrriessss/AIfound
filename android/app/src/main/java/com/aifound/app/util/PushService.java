package com.aifound.app.util;

import android.Manifest;
import android.app.PendingIntent;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;

import androidx.annotation.NonNull;
import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;
import androidx.core.content.ContextCompat;

import com.aifound.app.R;
import com.aifound.app.ui.LoginActivity;
import com.google.firebase.messaging.FirebaseMessagingService;
import com.google.firebase.messaging.RemoteMessage;

import java.util.Map;

/**
 * S05 푸시 받기 (이민서). match-server/ANDROID.md 4번.
 * 앱이 꺼져 있거나 뒤에 있으면 시스템이 알림을 띄우고, 누르면 LoginActivity extras 로 data 가 온다.
 * 앱이 켜져 있을 때만 onMessageReceived 로 오므로 여기서 직접 알림을 만든다.
 */
public class PushService extends FirebaseMessagingService {

    @Override
    public void onNewToken(@NonNull String token) {
        Push.sendToken(this, token);
    }

    @Override
    public void onMessageReceived(@NonNull RemoteMessage msg) {
        if (Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(this,
                Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            return;   // 알림 허용 안 함 (S27 알림함에는 서버가 따로 저장해 둠)
        }
        Map<String, String> data = msg.getData();
        RemoteMessage.Notification n = msg.getNotification();
        String title = n != null && n.getTitle() != null ? n.getTitle() : data.getOrDefault("title", "AIfound");
        String body = n != null && n.getBody() != null ? n.getBody() : data.getOrDefault("body", "");

        // 누르면 LoginActivity → (로그인돼 있으면) 홈 + 대상 화면. 앱이 꺼져 있을 때와 같은 길로 보낸다
        Intent open = new Intent(this, LoginActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
        for (Map.Entry<String, String> e : data.entrySet()) open.putExtra(e.getKey(), e.getValue());
        int id = (int) (System.currentTimeMillis() & 0x7fffffff);
        PendingIntent pi = PendingIntent.getActivity(this, id, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        Push.createChannel(this);
        NotificationCompat.Builder b = new NotificationCompat.Builder(this, Push.CHANNEL)
                .setSmallIcon(R.drawable.ic_bell)
                .setColor(getColor(R.color.accent))
                .setContentTitle(title)
                .setContentText(body)
                .setStyle(new NotificationCompat.BigTextStyle().bigText(body))   // 05: 물건 · 장소 · 일치율 + "이유" 두 줄
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setAutoCancel(true)
                .setContentIntent(pi);
        try {
            NotificationManagerCompat.from(this).notify(id, b.build());
        } catch (SecurityException ignored) {
            // 권한이 막 바뀐 경우
        }
    }
}
