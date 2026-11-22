package com.aifound.app.ui;

import android.content.Intent;
import android.os.Bundle;
import android.text.TextUtils;
import android.widget.ArrayAdapter;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.Spinner;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

import com.aifound.app.R;
import com.aifound.app.data.Catalog;
import com.aifound.app.data.FoundDraft;
import com.aifound.app.net.Models;
import com.aifound.app.util.ImageUtils;
import com.aifound.app.util.Steps;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** S12 AI 인식 결과 확인·수정 (종류, 세부 종류, 브랜드, 색, 특징). */
public class AiTagsActivity extends AppCompatActivity {

    private EditText etTitle, etSub, etBrand, etFeatures;
    private Spinner spCategory, spColor;
    private FoundDraft draft;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        draft = FoundDraft.get();
        if (draft.attributes == null) { finish(); return; }

        setContentView(R.layout.activity_ai_tags);
        Steps.header(this, "AI 인식 결과", 3);

        etTitle = findViewById(R.id.etTitle);
        etSub = findViewById(R.id.etSubcategory);
        etBrand = findViewById(R.id.etBrand);
        etFeatures = findViewById(R.id.etFeatures);
        spCategory = findViewById(R.id.spCategory);
        spColor = findViewById(R.id.spColor);
        ((ImageView) findViewById(R.id.ivThumb)).setImageBitmap(ImageUtils.load(draft.imageFile));

        spCategory.setAdapter(adapter(Catalog.CATEGORIES));
        spColor.setAdapter(adapter(Catalog.COLORS));

        Models.ItemAttributes a = draft.attributes;
        etTitle.setText(a.title);
        spCategory.setSelection(Catalog.indexOf(Catalog.CATEGORIES, a.category));
        etSub.setText(a.subcategory);
        etBrand.setText(a.brand);
        spColor.setSelection(Catalog.indexOf(Catalog.COLORS, a.color != null ? a.color : "기타"));
        if (a.features != null) etFeatures.setText(TextUtils.join(", ", a.features));
        if (a.confidence != null) {
            ((TextView) findViewById(R.id.tvConfidence)).setText(String.format(Locale.KOREA,
                    "AI 확신도  종류 %d%% · 브랜드 %d%% · 색 %d%%",
                    Math.round(a.confidence.category * 100), Math.round(a.confidence.brand * 100),
                    Math.round(a.confidence.color * 100)));
        }

        findViewById(R.id.btnNext).setOnClickListener(v -> {
            if (etTitle.getText().toString().trim().isEmpty()) {
                etTitle.setError("물건 이름을 입력해 주세요");
                return;
            }
            apply();
            startActivity(new Intent(this, FoundInfoActivity.class));
        });
    }

    private ArrayAdapter<String> adapter(String[] items) {
        ArrayAdapter<String> ad = new ArrayAdapter<>(this, android.R.layout.simple_spinner_item, items);
        ad.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        return ad;
    }

    /** 화면 값 → draft.attributes (서버로 보낼 최종 속성) */
    private void apply() {
        Models.ItemAttributes a = draft.attributes;
        a.title = etTitle.getText().toString().trim();
        a.category = (String) spCategory.getSelectedItem();
        a.subcategory = emptyToNull(etSub.getText().toString());
        a.brand = emptyToNull(etBrand.getText().toString());

        a.color = (String) spColor.getSelectedItem();

        List<String> features = new ArrayList<>();
        for (String f : etFeatures.getText().toString().split("[,，]")) {
            String t = f.trim();
            if (!t.isEmpty() && features.size() < 6) features.add(t.length() > 15 ? t.substring(0, 15) : t);
        }
        a.features = features;
    }

    private static String emptyToNull(String s) {
        String t = s.trim();
        return t.isEmpty() ? null : t;
    }
}
