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
import com.aifound.app.util.Push;
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
                        + "회원 탈퇴하면 분실 신고와 수령 기록이 지워져요."));
        findViewById(R.id.menuTerms).setOnClickListener(v -> info("이용약관", TERMS));
        findViewById(R.id.menuServer).setOnClickListener(v -> editServer());
        findViewById(R.id.menuLogout).setOnClickListener(v -> new AlertDialog.Builder(this)
                .setTitle("로그아웃할까요?")
                .setPositiveButton("로그아웃", (d, w) -> goLogin())
                .setNegativeButton("취소", null)
                .show());
        findViewById(R.id.menuDelete).setOnClickListener(v -> confirmDelete());
    }

    /** S28 이용약관. 숭실대 학생 대상 학기 프로젝트(AIfound) 기준 */
    private static final String TERMS =
            "제1조 (목적)\n"
            + "이 약관은 숭실대학교 구성원이 AIfound(이하 '서비스')로 교내 분실물·습득물을 등록하고 찾는 데 필요한 이용 조건을 정해요.\n\n"
            + "제2조 (이용 대상)\n"
            + "학교 메일(@soongsil.ac.kr)로 본인 인증을 마친 사람만 이용할 수 있어요. 다른 사람의 메일로 가입하거나 계정을 빌려 주면 안 돼요.\n\n"
            + "제3조 (습득물 등록)\n"
            + "① 습득물은 사진·장소·시간을 사실대로 등록하고, 실제 물건은 안내된 교내 보관함(행정실)에 맡겨요.\n"
            + "② 학생증·카드 등에 보이는 이름·학번·얼굴 같은 개인정보는 가린 뒤 올려요. AI가 먼저 가려 주지만 마지막 확인은 등록한 사람이 해요.\n"
            + "③ 습득물을 등록했다고 해서 소유권이 생기지 않아요.\n\n"
            + "제4조 (분실 신고와 매칭)\n"
            + "① 분실 신고 내용은 비슷한 습득물을 찾는 데만 써요.\n"
            + "② AI 매칭 결과와 일치율은 참고용이에요. 실제 내 물건인지는 수령할 때 본인이 확인해야 해요.\n\n"
            + "제5조 (수령)\n"
            + "① '내 물건이에요'를 누르면 수령 대기가 되고, 7일 안에 보관함에서 학교 메일 확인과 수령 코드로 찾아가요.\n"
            + "② 기한이 지나면 요청이 풀려 다른 사람이 신청할 수 있어요.\n"
            + "③ 내 물건이 아닌 것을 알면서 수령 요청하거나 받아 가면 안 되며, 이 경우 학교 규정과 법에 따른 책임은 본인에게 있어요.\n\n"
            + "제6조 (금지 행위)\n"
            + "거짓 등록·신고, 다른 사람의 개인정보 수집·유포, 서비스를 방해하는 행위는 금지돼요. 어기면 이용이 제한될 수 있어요.\n\n"
            + "제7조 (알림)\n"
            + "매칭 후보·수령 기한·주인 확인 소식을 푸시와 알림함으로 보내요. 알림 설정에서 끄거나 방해 금지 시간을 정할 수 있어요.\n\n"
            + "제8조 (책임의 한계)\n"
            + "서비스는 분실물을 찾도록 돕는 도구이며, 보관 중 물건의 상태나 매칭 결과를 보장하지 않아요. 물건 보관 책임은 보관함을 운영하는 부서에 있어요.\n\n"
            + "제9조 (탈퇴)\n"
            + "설정 > 회원 탈퇴로 언제든 탈퇴할 수 있어요. 분실 신고와 수령 기록은 지워지고, 등록한 습득물은 보관함 운영을 위해 등록자 정보만 지운 채 남아요.\n\n"
            + "부칙\n"
            + "이 약관은 2026년 12월 1일부터 적용해요.";

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
        Push.unregister(this);   // 이 폰으로 이전 계정 알림이 오지 않게
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
