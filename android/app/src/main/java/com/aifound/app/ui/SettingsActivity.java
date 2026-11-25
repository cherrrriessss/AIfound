package com.aifound.app.ui;

import android.content.Intent;
import android.os.Bundle;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;

import com.aifound.app.BuildConfig;
import com.aifound.app.R;
import com.aifound.app.data.TokenStore;
import com.aifound.app.net.ApiCallback;
import com.aifound.app.net.ApiClient;
import com.aifound.app.net.Models;
import com.aifound.app.util.Fmt;
import com.aifound.app.util.Ui;

/**
 * S28 설정 (이민서). 와이어프레임 S28_Settings.
 * 프로필 수정(S03 재사용) · 학교 메일 · 알림 설정(S26) · 정보 · 앱 버전 · 로그아웃 · 회원 탈퇴(DELETE /me).
 * 로그아웃·탈퇴는 예전 임시 마이페이지(김준희)에서 옮겨 왔다.
 */
public class SettingsActivity extends AppCompatActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_settings);
        Ui.header(this, "설정");

        ((TextView) findViewById(R.id.tvEmail)).setText(TokenStore.email(this));
        ((TextView) findViewById(R.id.tvVersion)).setText(BuildConfig.VERSION_NAME);

        findViewById(R.id.menuProfile).setOnClickListener(v -> ProfileActivity.openEdit(this));
        findViewById(R.id.menuNoti).setOnClickListener(v -> startActivity(new Intent(this, NotiSettingActivity.class)));
        findViewById(R.id.menuPrivacy).setOnClickListener(v -> info("개인정보 처리방침",
                "AIfound 가 다루는 정보 (요약)\n\n"
                        + "· 학교 메일 주소, 이름, 학과: 로그인과 수령 시 본인 확인\n"
                        + "· 습득물 사진: 개인정보(이름·학번·얼굴 등)를 가린 뒤 저장, 사진 위치 정보(EXIF)는 지워서 보냄\n"
                        + "· 분실 신고 내용: 비슷한 습득물을 찾는 데만 사용\n"
                        + "· 수령 기록: 누가 언제 어디서 받았는지\n\n"
                        + "회원 탈퇴하면 분실 신고와 수령 기록이 지워져요.\n"
                        + "(최종 문서는 팀에서 확정 후 바꿔 주세요)"));
        findViewById(R.id.menuTerms).setOnClickListener(v -> info("이용약관",
                "[이용약관 본문 — 팀에서 확정 후 추가]"));
        findViewById(R.id.menuServer).setOnClickListener(v -> editServer());
        findViewById(R.id.menuLogout).setOnClickListener(v -> new AlertDialog.Builder(this)
                .setTitle("로그아웃할까요?")
                .setPositiveButton("로그아웃", (d, w) -> goLogin())
                .setNegativeButton("취소", null)
                .show());
        findViewById(R.id.menuDelete).setOnClickListener(v -> confirmDelete());
    }

    private void info(String title, String body) {
        new AlertDialog.Builder(this).setTitle(title).setMessage(body).setPositiveButton("확인", null).show();
    }

    /** 실제 폰에서 컴퓨터 서버 주소 바꾸기 (로그인 화면 '서버 설정'과 같은 값). 매칭 서버는 포트만 8000 */
    private void editServer() {
        EditText input = new EditText(this);
        input.setText(TokenStore.baseUrl(this));
        input.setSingleLine();
        int pad = Fmt.dp(this, 20);
        input.setPadding(pad, pad / 2, pad, pad / 2);
        new AlertDialog.Builder(this)
                .setTitle("서버 주소")
                .setMessage("김준희 서버(8001) 주소. 매칭 서버는 같은 주소의 8000번을 써요.")
                .setView(input)
                .setPositiveButton("저장", (d, w) -> {
                    TokenStore.saveBaseUrl(this, input.getText().toString());
                    Toast.makeText(this, "저장했어요: " + TokenStore.baseUrl(this), Toast.LENGTH_SHORT).show();
                })
                .setNegativeButton("취소", null)
                .show();
    }

    private void goLogin() {
        TokenStore.clearToken(this);
        Intent i = new Intent(this, LoginActivity.class);
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
        startActivity(i);
    }

    private void confirmDelete() {
        new AlertDialog.Builder(this)
                .setTitle("회원 탈퇴")
                .setMessage("내 분실 신고와 수령 기록이 삭제돼요.\n등록한 습득물은 보관함에 있으니 남겨 두고, 등록자 정보만 지워요.\n\n정말 탈퇴할까요?")
                .setPositiveButton("탈퇴", (d, w) -> ApiClient.get(this).deleteMe()
                        .enqueue(new ApiCallback<Models.Ok>(this) {
                            @Override public void ok(Models.Ok body) {
                                Toast.makeText(SettingsActivity.this, "탈퇴했어요", Toast.LENGTH_SHORT).show();
                                goLogin();
                            }
                        }))
                .setNegativeButton("취소", null)
                .show();
    }
}
