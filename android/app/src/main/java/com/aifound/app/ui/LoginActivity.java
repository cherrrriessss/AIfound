package com.aifound.app.ui;

import android.content.Intent;
import android.os.Bundle;
import android.os.CountDownTimer;
import android.text.InputType;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;

import com.aifound.app.R;
import com.aifound.app.data.TokenStore;
import com.aifound.app.util.Push;
import com.aifound.app.net.ApiCallback;
import com.aifound.app.net.ApiClient;
import com.aifound.app.net.Models;
import com.google.android.material.button.MaterialButton;

/** S02 학교 메일 로그인: 아이디 → 인증코드 받기 → 6자리 입력 → 로그인 */
public class LoginActivity extends AppCompatActivity {

    private EditText etId, etCode;
    private TextView tvTimer, tvResend;
    private MaterialButton btnSendCode, btnLogin;
    private CountDownTimer expiryTimer, resendTimer;
    private String requestedEmail;   // 서버가 정리해 준 전체 메일 주소

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // 이미 로그인돼 있으면 바로 홈으로
        if (TokenStore.token(this) != null) {
            // S05 푸시를 눌러서 들어왔으면 홈 위에 그 화면(매칭 상세 등)을 바로 연다
            if (Push.hasTarget(getIntent().getExtras())) Push.openFromLaunch(this, getIntent().getExtras());
            else startActivity(new Intent(this, HomeActivity.class));
            finish();
            return;
        }

        setContentView(R.layout.activity_login);
        etId = findViewById(R.id.etId);
        etCode = findViewById(R.id.etCode);
        tvTimer = findViewById(R.id.tvTimer);
        tvResend = findViewById(R.id.tvResend);
        btnSendCode = findViewById(R.id.btnSendCode);
        btnLogin = findViewById(R.id.btnLogin);

        btnSendCode.setOnClickListener(v -> sendCode());
        tvResend.setOnClickListener(v -> sendCode());
        btnLogin.setOnClickListener(v -> login());
        findViewById(R.id.tvServer).setOnClickListener(v -> showServerDialog());
    }

    private void sendCode() {
        String id = etId.getText().toString().trim();
        if (id.isEmpty()) {
            etId.setError("학번 또는 아이디를 입력해 주세요");
            return;
        }
        btnSendCode.setEnabled(false);
        ApiClient.get(this).requestCode(new Models.RequestCodeIn(id))
                .enqueue(new ApiCallback<Models.RequestCodeOut>(this) {
                    @Override public void ok(Models.RequestCodeOut body) {
                        requestedEmail = body.email;
                        Toast.makeText(LoginActivity.this, body.email + " 로 인증코드를 보냈어요", Toast.LENGTH_LONG).show();
                        startExpiryTimer(body.expiresIn);
                        startResendCooldown(body.resendAfter);
                        etCode.requestFocus();
                    }

                    @Override public void fail(String message) {
                        super.fail(message);
                        btnSendCode.setEnabled(true);
                    }
                });
    }

    private void login() {
        String code = etCode.getText().toString().trim();
        if (code.length() < 6 || code.length() > 10) {
            etCode.setError("메일로 받은 숫자를 입력해 주세요");
            return;
        }
        String email = requestedEmail != null ? requestedEmail : etId.getText().toString().trim();
        btnLogin.setEnabled(false);
        ApiClient.get(this).verify(new Models.VerifyIn(email, code))
                .enqueue(new ApiCallback<Models.TokenOut>(this) {
                    @Override public void ok(Models.TokenOut body) {
                        TokenStore.saveToken(LoginActivity.this, body.accessToken);
                        TokenStore.saveEmail(LoginActivity.this, body.user != null ? body.user.email : email);
                        Intent next = new Intent(LoginActivity.this,
                                body.isNewUser ? ProfileActivity.class : HomeActivity.class);
                        startActivity(next);
                        finish();
                    }

                    @Override public void fail(String message) {
                        super.fail(message);
                        btnLogin.setEnabled(true);
                    }
                });
    }

    /** 인증코드 유효시간 표시 (S02 '04:59') */
    private void startExpiryTimer(int seconds) {
        if (expiryTimer != null) expiryTimer.cancel();
        expiryTimer = new CountDownTimer(seconds * 1000L, 1000) {
            @Override public void onTick(long ms) {
                long s = ms / 1000;
                tvTimer.setText(String.format(java.util.Locale.KOREA, "%02d:%02d", s / 60, s % 60));
            }

            @Override public void onFinish() { tvTimer.setText("만료"); }
        }.start();
    }

    /** 재전송 대기 (서버도 60초 제한) */
    private void startResendCooldown(int seconds) {
        if (resendTimer != null) resendTimer.cancel();
        tvResend.setEnabled(false);
        resendTimer = new CountDownTimer(seconds * 1000L, 1000) {
            @Override public void onTick(long ms) {
                tvResend.setText("메일이 안 왔나요? " + (ms / 1000) + "초 후 다시 보내기");
            }

            @Override public void onFinish() {
                tvResend.setEnabled(true);
                btnSendCode.setEnabled(true);
                tvResend.setText("메일이 안 왔나요? 다시 보내기");
            }
        }.start();
    }

    /** 실제 폰에서 쓸 때: 같은 와이파이의 내 컴퓨터 IP:8000 입력 */
    private void showServerDialog() {
        EditText input = new EditText(this);
        input.setInputType(InputType.TYPE_TEXT_VARIATION_URI);
        input.setText(TokenStore.baseUrl(this));
        int pad = (int) (20 * getResources().getDisplayMetrics().density);
        input.setPadding(pad, pad / 2, pad, pad / 2);
        new AlertDialog.Builder(this)
                .setTitle("서버 주소")
                .setMessage("에뮬레이터: http://10.0.2.2:8000\n실제 폰: http://<내 컴퓨터 IP>:8000")
                .setView(input)
                .setPositiveButton("저장", (d, w) -> {
                    TokenStore.saveBaseUrl(this, input.getText().toString());
                    Toast.makeText(this, "저장했어요: " + TokenStore.baseUrl(this), Toast.LENGTH_SHORT).show();
                })
                .setNegativeButton("취소", null)
                .show();
    }

    @Override
    protected void onDestroy() {
        if (expiryTimer != null) expiryTimer.cancel();
        if (resendTimer != null) resendTimer.cancel();
        super.onDestroy();
    }
}
