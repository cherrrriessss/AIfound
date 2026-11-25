package com.aifound.app.ui;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.os.Bundle;
import android.os.CountDownTimer;
import android.view.View;
import android.widget.ImageView;
import android.widget.TextView;

import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;

import com.aifound.app.R;
import com.aifound.app.data.TokenStore;
import com.aifound.app.net.ApiCallback;
import com.aifound.app.net.ApiClient;
import com.aifound.app.net.MatchModels;
import com.aifound.app.util.Fmt;
import com.aifound.app.util.Ui;
import com.google.zxing.BarcodeFormat;
import com.google.zxing.EncodeHintType;
import com.google.zxing.common.BitMatrix;
import com.google.zxing.qrcode.QRCodeWriter;

import java.time.Duration;
import java.time.ZonedDateTime;
import java.util.EnumMap;
import java.util.Map;

/**
 * S20 수령 안내·본인 확인 (이민서). 와이어프레임 S20_Claim.
 * GET /matches/{id}/pickup → 물건, 기한(7일), 보관함, 수령 코드(6자리 + QR).
 * 코드는 10분마다 바뀐다: expires_in 초 뒤 GET /matches/{id}/pickup/code 로 다시 받는다.
 * '수령 완료 확인' → GET /matches/{id}/pickup/status (행정실이 코드를 확인하면 true) → S25.
 */
public class ClaimActivity extends AppCompatActivity {

    private static final String EXTRA_ID = "match_id";

    public static void open(Activity from, String matchId) {
        from.startActivity(intent(from, matchId));
    }

    /** S05 푸시를 눌렀을 때도 같은 화면 (util/Push) */
    public static Intent intent(android.content.Context c, String matchId) {
        return new Intent(c, ClaimActivity.class).putExtra(EXTRA_ID, matchId);
    }

    private String matchId;
    private MatchModels.LockerInfo locker;
    private CountDownTimer timer;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_claim);
        Ui.header(this, "수령 안내");
        matchId = getIntent().getStringExtra(EXTRA_ID);
        if (matchId == null) {
            finish();
            return;
        }
        ((TextView) findViewById(R.id.tvEmail)).setText(TokenStore.email(this) + " 인증됨");
        findViewById(R.id.btnMap).setOnClickListener(v -> {
            if (locker != null) StorageMapActivity.open(this, locker);
        });
        findViewById(R.id.btnCheck).setOnClickListener(v -> checkReceived());
        loadGuide();
    }

    @Override
    protected void onDestroy() {
        if (timer != null) timer.cancel();
        super.onDestroy();
    }

    private void loadGuide() {
        ApiClient.match(this).pickupGuide(matchId).enqueue(new ApiCallback<MatchModels.PickupGuide>(this) {
            @Override public void ok(MatchModels.PickupGuide g) { show(g); }
        });
    }

    private void show(MatchModels.PickupGuide g) {
        if (g.item != null) {
            Fmt.photo(findViewById(R.id.ivPhoto), g.item.photoUrl);
            ((TextView) findViewById(R.id.tvName)).setText(g.item.name);
        }
        ((TextView) findViewById(R.id.tvDeadline)).setText(deadlineText(g.deadline));

        for (MatchModels.PickupStep s : g.steps) {
            if (s.locker != null && s.locker.name != null) locker = s.locker;
        }
        TextView tvLocker = findViewById(R.id.tvLocker);
        if (locker != null) {
            tvLocker.setText(locker.name + (locker.hours != null ? " · " + locker.hours : ""));
        } else {
            tvLocker.setText("보관함 정보가 없어요. 습득물 상세에서 확인해 주세요.");
            findViewById(R.id.btnMap).setVisibility(View.GONE);
        }
        if (g.code != null) showCode(g.code);
    }

    /** '수령 대기 중 · 7일 내 수령 (12/2까지)' */
    private static String deadlineText(String iso) {
        ZonedDateTime d = Fmt.parse(iso);
        if (d == null) return "수령 대기 중";
        long days = Math.max(0, Duration.between(ZonedDateTime.now(d.getZone()), d).toDays());
        return "수령 대기 중 · " + (days > 0 ? days + "일 안에" : "오늘까지") + " 수령 (" + Fmt.shortDate(iso) + "까지)";
    }

    // ---------------- 수령 코드 (10분마다 갱신) ----------------

    private void showCode(MatchModels.PickupCode c) {
        ((TextView) findViewById(R.id.tvCode)).setText(c.display != null ? c.display : c.code);
        ((ImageView) findViewById(R.id.ivQr)).setImageBitmap(qr(c.qr != null ? c.qr : c.code, Fmt.dp(this, 160)));
        if (timer != null) timer.cancel();
        TextView remain = findViewById(R.id.tvRemain);
        timer = new CountDownTimer(Math.max(1, c.expiresIn) * 1000L, 1000) {
            @Override public void onTick(long ms) {
                long s = ms / 1000;
                remain.setText(String.format(java.util.Locale.KOREA, "10분마다 갱신 · 남은 시간 %02d:%02d", s / 60, s % 60));
            }

            @Override public void onFinish() { refreshCode(); }
        }.start();
    }

    private void refreshCode() {
        ApiClient.match(this).pickupCode(matchId).enqueue(new ApiCallback<MatchModels.PickupCode>(this) {
            @Override public void ok(MatchModels.PickupCode c) { showCode(c); }
        });
    }

    /** QR 이미지 만들기 (zxing). 행정실 담당자 화면이 'AIFOUND:<match_id>:<code>' 를 읽는다. */
    static Bitmap qr(String text, int size) {
        try {
            Map<EncodeHintType, Object> hints = new EnumMap<>(EncodeHintType.class);
            hints.put(EncodeHintType.MARGIN, 1);
            BitMatrix m = new QRCodeWriter().encode(text, BarcodeFormat.QR_CODE, size, size, hints);
            int w = m.getWidth(), h = m.getHeight();
            int[] px = new int[w * h];
            for (int y = 0; y < h; y++) {
                for (int x = 0; x < w; x++) px[y * w + x] = m.get(x, y) ? Color.BLACK : Color.WHITE;
            }
            return Bitmap.createBitmap(px, w, h, Bitmap.Config.ARGB_8888);
        } catch (Exception e) {
            return null;
        }
    }

    // ---------------- 수령 완료 확인 ----------------

    private void checkReceived() {
        ApiClient.match(this).pickupStatus(matchId).enqueue(new ApiCallback<MatchModels.PickupStatus>(this) {
            @Override public void ok(MatchModels.PickupStatus s) {
                if (s.received) {
                    new AlertDialog.Builder(ClaimActivity.this)
                            .setTitle("수령이 기록됐어요")
                            .setMessage("물건을 찾아서 다행이에요!")
                            .setPositiveButton("수령 기록 보기", (d, w) -> {
                                startActivity(new Intent(ClaimActivity.this, HistoryActivity.class));
                                finish();
                            })
                            .setCancelable(false)
                            .show();
                } else {
                    new AlertDialog.Builder(ClaimActivity.this)
                            .setTitle("아직 확인 전이에요")
                            .setMessage("보관함 담당자에게 수령 코드를 보여주면 수령 완료로 바뀌어요.")
                            .setPositiveButton("확인", null)
                            .show();
                }
            }
        });
    }
}
