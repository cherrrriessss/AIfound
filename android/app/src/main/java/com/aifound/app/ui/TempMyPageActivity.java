package com.aifound.app.ui;

import android.content.Intent;
import android.os.Bundle;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;

import com.aifound.app.R;
import com.aifound.app.data.FoundDraft;
import com.aifound.app.data.TokenStore;
import com.aifound.app.net.ApiCallback;
import com.aifound.app.net.ApiClient;
import com.aifound.app.net.Models;

import java.util.List;

/**
 * 임시 마이페이지 (김준희 파트 확인용 홈을 옮김). S22 마이페이지를 만들면 지운다.
 * 여기서 '주운 물건 등록하기' → S10~S15 흐름을 시험할 수 있다.
 */
public class TempMyPageActivity extends AppCompatActivity {

    private LinearLayout list;
    private TextView tvHello;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_temp_my);
        list = findViewById(R.id.myFoundList);
        tvHello = findViewById(R.id.tvHello);

        findViewById(R.id.btnRegister).setOnClickListener(v -> {
            FoundDraft.reset();
            startActivity(new Intent(this, PhotoActivity.class));
        });
        findViewById(R.id.tvLogout).setOnClickListener(v -> goLogin());
        findViewById(R.id.tvDeleteAccount).setOnClickListener(v -> confirmDelete());
    }

    private void goLogin() {
        TokenStore.clearToken(this);
        Intent i = new Intent(this, LoginActivity.class);
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
        startActivity(i);
    }

    /** S28 회원 탈퇴 */
    private void confirmDelete() {
        new AlertDialog.Builder(this)
                .setTitle("회원 탈퇴")
                .setMessage("내 분실 신고와 수령 기록이 삭제돼요.\n등록한 습득물은 보관함에 있으니 남겨 두고, 등록자 정보만 지워요.\n\n정말 탈퇴할까요?")
                .setPositiveButton("탈퇴", (d, w) -> ApiClient.get(this).deleteMe()
                        .enqueue(new ApiCallback<Models.Ok>(this) {
                            @Override public void ok(Models.Ok body) {
                                android.widget.Toast.makeText(TempMyPageActivity.this, "탈퇴했어요", android.widget.Toast.LENGTH_SHORT).show();
                                goLogin();
                            }
                        }))
                .setNegativeButton("취소", null)
                .show();
    }

    @Override
    protected void onResume() {
        super.onResume();
        ApiClient.get(this).me().enqueue(new ApiCallback<Models.Profile>(this) {
            @Override public void ok(Models.Profile body) {
                if (body.name == null || body.name.isEmpty()) {
                    startActivity(new Intent(TempMyPageActivity.this, ProfileActivity.class));
                    return;
                }
                tvHello.setText(body.name + "님, 안녕하세요");
            }
        });
        ApiClient.get(this).myFound().enqueue(new ApiCallback<List<Models.FoundOut>>(this) {
            @Override public void ok(List<Models.FoundOut> items) { showList(items); }
        });
        // S22 마이페이지 숫자 (확인용)
        ApiClient.get(this).summary().enqueue(new ApiCallback<Models.Summary>(this) {
            @Override public void ok(Models.Summary s) {
                ((TextView) findViewById(R.id.tvSummary)).setText(
                        "분실 신고 " + s.lostCount + "  ·  습득물 등록 " + s.foundCount
                                + "  ·  수령 완료 " + s.receivedCount
                                + "\n지금까지 " + s.returnedCount + "명에게 물건을 돌려줬어요");
            }
        });
    }

    private void showList(List<Models.FoundOut> items) {
        list.removeAllViews();
        if (items.isEmpty()) {
            list.addView(row("아직 등록한 습득물이 없어요", null));
            return;
        }
        for (Models.FoundOut f : items) {
            String where = (f.building != null ? f.building : "") + (f.locationDetail != null ? " " + f.locationDetail : "");
            String locker = f.locker != null ? f.locker.name : "";
            String badge = f.displayLabel != null ? f.displayLabel : statusText(f.status);
            list.addView(row("[" + badge + "] " + f.title, where + " · " + matchText(f.matchStatus)
                    + "\n보관: " + locker));
        }
    }

    private TextView row(String title, String sub) {
        TextView tv = new TextView(this);
        tv.setText(sub == null ? title : title + "\n" + sub);
        tv.setTextSize(14);
        tv.setTextColor(getColor(R.color.ink));
        tv.setLineSpacing(0, 1.3f);
        int pad = (int) (14 * getResources().getDisplayMetrics().density);
        tv.setPadding(pad, pad, pad, pad);
        tv.setBackgroundResource(R.drawable.bg_card);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.topMargin = pad / 2;
        tv.setLayoutParams(lp);
        return tv;
    }

    private static String statusText(String status) {
        if ("stored".equals(status)) return "보관 중";
        if ("returned".equals(status)) return "주인에게 돌아감";
        return status;
    }

    /** 15 화면과 같은 매칭 진행 상태 (주희선 서버가 바꿈) */
    private static String matchText(String s) {
        if ("searching".equals(s)) return "주인 찾는 중";
        if ("notified".equals(s)) return "주인에게 알림 보냄";
        if ("no_match".equals(s)) return "아직 비슷한 신고 없음";
        return "매칭 대기";
    }
}
