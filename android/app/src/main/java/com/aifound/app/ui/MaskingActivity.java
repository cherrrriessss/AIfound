package com.aifound.app.ui;

import android.content.Intent;
import android.os.Bundle;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.aifound.app.R;
import com.aifound.app.data.FoundDraft;
import com.aifound.app.util.ImageUtils;
import com.aifound.app.util.Steps;
import com.google.android.material.button.MaterialButton;

import java.util.List;

/** S11 개인정보 가리기: 자동 가림 / 직접 가리기 / 되돌리기. 감지 영역이 남아 있으면 다음으로 못 감. */
public class MaskingActivity extends AppCompatActivity {

    private MaskEditorView editor;
    private MaterialButton btnDraw;
    private FoundDraft draft;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        draft = FoundDraft.get();
        if (draft.imageFile == null || draft.analysis == null) { finish(); return; }

        setContentView(R.layout.activity_masking);
        Steps.header(this, "개인정보 가리기", 2);

        TextView title = findViewById(R.id.tvBannerTitle);
        TextView body = findViewById(R.id.tvBannerBody);
        List<int[]> detected = draft.detectedRegions();
        if (!detected.isEmpty()) {
            title.setText("개인정보가 보여요");
            body.setText(draft.analysis.piiWarning != null ? draft.analysis.piiWarning
                    : "가린 뒤에 등록돼요. '자동 가림'을 눌러 보세요.");
        } else {
            title.setText("감지된 개인정보가 없어요");
            body.setText("이름·학번·얼굴이 보이면 '직접 가리기'로 가려 주세요.");
            findViewById(R.id.tvMaskHint).setVisibility(android.view.View.GONE);
        }

        editor = findViewById(R.id.maskEditor);
        editor.setData(ImageUtils.load(draft.imageFile), detected, draft.masks);

        findViewById(R.id.btnAutoMask).setOnClickListener(v -> {
            if (detected.isEmpty()) {
                Toast.makeText(this, "AI가 찾은 개인정보가 없어요", Toast.LENGTH_SHORT).show();
                return;
            }
            for (int[] d : draft.uncoveredRegions()) draft.masks.add(d.clone());
            editor.refresh();
        });

        btnDraw = findViewById(R.id.btnDraw);
        btnDraw.setOnClickListener(v -> {
            editor.setDrawMode(!editor.isDrawMode());
            btnDraw.setText(editor.isDrawMode() ? "그리는 중" : "직접 가리기");
            if (editor.isDrawMode()) Toast.makeText(this, "가릴 부분을 손가락으로 끌어서 사각형을 그려요", Toast.LENGTH_SHORT).show();
        });

        findViewById(R.id.btnUndo).setOnClickListener(v -> {
            if (!draft.masks.isEmpty()) {
                draft.masks.remove(draft.masks.size() - 1);
                editor.refresh();
            }
        });

        findViewById(R.id.btnNext).setOnClickListener(v -> {
            if (!draft.uncoveredRegions().isEmpty()) {
                Toast.makeText(this, "아직 가리지 않은 개인정보가 있어요 (주황 점선)", Toast.LENGTH_LONG).show();
                return;
            }
            startActivity(new Intent(this, AiTagsActivity.class));
        });
    }
}
