package com.aifound.app.ui;

import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.aifound.app.R;
import com.aifound.app.data.FoundDraft;
import com.aifound.app.net.ApiCallback;
import com.aifound.app.net.ApiClient;
import com.aifound.app.net.Models;
import com.aifound.app.util.Steps;
import com.google.android.material.button.MaterialButton;

import java.text.SimpleDateFormat;
import java.util.List;
import java.util.Locale;

/** S14 어디에 맡길까요? → '등록하기' 로 서버 POST /found */
public class StorageActivity extends AppCompatActivity {

    private RadioGroup rg;
    private MaterialButton btnSubmit;
    private FoundDraft draft;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        draft = FoundDraft.get();
        setContentView(R.layout.activity_storage);
        Steps.header(this, "어디에 맡길까요?", 5);

        rg = findViewById(R.id.rgStorages);
        btnSubmit = findViewById(R.id.btnSubmit);
        ((TextView) findViewById(R.id.tvNearHint)).setText("습득 장소(" + draft.building + ")와 같은 건물을 먼저 보여드려요");

        String when = new SimpleDateFormat("M/d HH:mm", Locale.KOREA).format(draft.foundAt.getTime());
        ((TextView) findViewById(R.id.tvSummary)).setText("등록 내용 확인\n" + draft.attributes.title + " · "
                + draft.building + (draft.locationDetail != null ? " " + draft.locationDetail : "") + " · " + when + "경");

        ApiClient.get(this).lockers(draft.building).enqueue(new ApiCallback<List<Models.Locker>>(this) {
            @Override public void ok(List<Models.Locker> body) { show(body); }
        });
        btnSubmit.setOnClickListener(v -> submit());
    }

    private void show(List<Models.Locker> lockers) {
        rg.removeAllViews();
        int pad = (int) (14 * getResources().getDisplayMetrics().density);
        for (Models.Locker s : lockers) {
            RadioButton rb = new RadioButton(this);
            rb.setId(View.generateViewId());
            rb.setTag(s);
            String text = s.name + (s.code != null ? " (" + s.code + ")" : "")
                    + (s.hours != null ? "\n" + s.hours : "")
                    + (s.sameBuilding ? "\n가장 가까움" : "");
            rb.setText(text);
            rb.setTextSize(15);
            rb.setPadding(pad / 2, pad, pad, pad);
            rb.setBackgroundResource(R.drawable.bg_card);
            RadioGroup.LayoutParams lp = new RadioGroup.LayoutParams(
                    RadioGroup.LayoutParams.MATCH_PARENT, RadioGroup.LayoutParams.WRAP_CONTENT);
            lp.bottomMargin = pad / 2;
            rg.addView(rb, lp);
            if (s.id.equals(draft.lockerId) || (draft.lockerId == null && rg.getCheckedRadioButtonId() == -1)) {
                rb.setChecked(true);   // 목록 맨 위(같은 건물)를 기본 선택
            }
        }
    }

    private void submit() {
        RadioButton checked = rg.findViewById(rg.getCheckedRadioButtonId());
        if (checked == null) {
            Toast.makeText(this, "보관함을 골라 주세요", Toast.LENGTH_SHORT).show();
            return;
        }
        Models.Locker s = (Models.Locker) checked.getTag();
        draft.lockerId = s.id;
        draft.lockerName = s.name;

        Models.FoundCreateIn body = new Models.FoundCreateIn();
        body.attributes = draft.attributes;
        body.building = draft.building;
        body.locationDetail = draft.locationDetail;
        body.foundAt = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssXXX", Locale.US).format(draft.foundAt.getTime());
        body.description = draft.description;
        body.lockerId = s.id;
        body.maskBoxes = draft.maskBoxes();

        btnSubmit.setEnabled(false);
        btnSubmit.setText("등록하는 중…");
        ApiClient.get(this).createFound(ApiClient.imagePart(draft.imageFile), ApiClient.jsonPart(body))
                .enqueue(new ApiCallback<Models.FoundOut>(this) {
                    @Override public void ok(Models.FoundOut result) {
                        draft.result = result;
                        Intent i = new Intent(StorageActivity.this, FoundDoneActivity.class);
                        i.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP);
                        startActivity(i);
                    }

                    @Override public void fail(String message) {
                        super.fail(message);
                        btnSubmit.setEnabled(true);
                        btnSubmit.setText("등록하기");
                    }
                });
    }
}
