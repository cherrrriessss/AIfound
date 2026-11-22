package com.aifound.app.ui;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.EditText;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.recyclerview.widget.GridLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.aifound.app.R;
import com.aifound.app.data.Catalog;
import com.aifound.app.net.ApiCallback;
import com.aifound.app.net.ApiClient;
import com.aifound.app.net.Models;
import com.aifound.app.util.Fmt;
import com.aifound.app.util.Steps;
import com.aifound.app.util.TabBar;

import java.util.ArrayList;
import java.util.List;

/**
 * S07 습득물 찾아보기 (이민서). 와이어프레임 S07_FoundList.
 * 서버 GET /found 사용: q(검색) + 종류·색·건물·날짜 필터, 최신순, 20개씩 이어서 불러오기.
 */
public class FoundListActivity extends AppCompatActivity {

    private static final int PAGE_SIZE = 20;
    private static final String[] DATE_LABELS = {"전체", "오늘", "최근 3일", "최근 7일", "최근 30일"};
    private static final int[] DATE_DAYS = {-1, 0, 2, 6, 29};

    // 현재 필터 (null = 전체)
    private String q, category, color, building;
    private int dateIdx = 0;
    private List<String> buildings = new ArrayList<>();

    private final List<Models.FoundOut> items = new ArrayList<>();
    private int page = 0, total = 0;
    private boolean loading = false;
    private int requestSeq = 0;      // 필터를 빨리 바꿀 때 늦게 온 옛 응답 무시

    private Adapter adapter;
    private TextView tvCount, tvEmpty, fCategory, fColor, fBuilding, fDate;
    private View progress;
    private EditText etSearch;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable searchLater = this::applySearchText;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_found_list);
        Steps.header(this, "습득물 찾아보기", 0);
        TabBar.setup(this, TabBar.HOME);

        tvCount = findViewById(R.id.tvCount);
        tvEmpty = findViewById(R.id.tvEmpty);
        progress = findViewById(R.id.progress);
        fCategory = findViewById(R.id.fCategory);
        fColor = findViewById(R.id.fColor);
        fBuilding = findViewById(R.id.fBuilding);
        fDate = findViewById(R.id.fDate);

        setupSearch();
        setupFilters();
        setupList();

        ApiClient.get(this).buildings().enqueue(new ApiCallback<List<String>>(this) {
            @Override public void ok(List<String> body) { buildings = body; }
        });
        reload();
    }

    // ---------------- 검색 ----------------
    private void setupSearch() {
        etSearch = findViewById(R.id.etSearch);
        View btnClear = findViewById(R.id.btnClear);
        etSearch.setOnEditorActionListener((v, actionId, e) -> {
            if (actionId == EditorInfo.IME_ACTION_SEARCH) {
                handler.removeCallbacks(searchLater);
                applySearchText();
                hideKeyboard();
                return true;
            }
            return false;
        });
        etSearch.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int a, int b, int c) {}
            @Override public void onTextChanged(CharSequence s, int a, int b, int c) {}
            @Override public void afterTextChanged(Editable s) {
                btnClear.setVisibility(s.length() > 0 ? View.VISIBLE : View.GONE);
                handler.removeCallbacks(searchLater);
                handler.postDelayed(searchLater, 400);   // 타자 멈추고 0.4초 뒤 검색
            }
        });
        btnClear.setOnClickListener(v -> etSearch.setText(""));
    }

    private void applySearchText() {
        String text = etSearch.getText().toString().trim();
        String next = text.isEmpty() ? null : text;
        if (next == null ? q == null : next.equals(q)) return;
        q = next;
        reload();
    }

    private void hideKeyboard() {
        InputMethodManager imm = (InputMethodManager) getSystemService(INPUT_METHOD_SERVICE);
        if (imm != null) imm.hideSoftInputFromWindow(etSearch.getWindowToken(), 0);
    }

    // ---------------- 필터 ----------------
    private void setupFilters() {
        fCategory.setOnClickListener(v -> pick("종류", withAll(Catalog.CATEGORIES), category, value -> category = value));
        fColor.setOnClickListener(v -> pick("색", withAll(Catalog.COLORS), color, value -> color = value));
        fBuilding.setOnClickListener(v -> {
            if (buildings.isEmpty()) {
                TabBar.soon(this, "건물 목록을 불러오는 중이에요");
                return;
            }
            pick("건물", withAll(buildings.toArray(new String[0])), building, value -> building = value);
        });
        fDate.setOnClickListener(v -> new AlertDialog.Builder(this)
                .setTitle("주운 날짜")
                .setSingleChoiceItems(DATE_LABELS, dateIdx, (d, which) -> {
                    d.dismiss();
                    if (which != dateIdx) {
                        dateIdx = which;
                        reload();
                    }
                })
                .show());
        paintFilters();
    }

    private interface Setter { void set(String value); }

    private static String[] withAll(String[] list) {
        String[] out = new String[list.length + 1];
        out[0] = "전체";
        System.arraycopy(list, 0, out, 1, list.length);
        return out;
    }

    /** 목록에서 하나 고르기. '전체' 를 고르면 null */
    private void pick(String title, String[] options, String current, Setter setter) {
        int checked = 0;
        for (int i = 1; i < options.length; i++) if (options[i].equals(current)) checked = i;
        final int before = checked;
        new AlertDialog.Builder(this)
                .setTitle(title)
                .setSingleChoiceItems(options, checked, (d, which) -> {
                    d.dismiss();
                    if (which == before) return;
                    setter.set(which == 0 ? null : options[which]);
                    reload();
                })
                .show();
    }

    private void paintFilters() {
        paint(fCategory, "종류", category);
        paint(fColor, "색", color);
        paint(fBuilding, "건물", building);
        paint(fDate, "날짜", dateIdx == 0 ? null : DATE_LABELS[dateIdx]);
    }

    /** 고른 값이 있으면 검정 버튼 + '종류: 지갑 ▾', 없으면 흰 버튼 + '종류 ▾' */
    private void paint(TextView tv, String name, String value) {
        boolean on = value != null;
        tv.setText(on ? name + ": " + value + " ▾" : name + " ▾");
        tv.setBackgroundResource(on ? R.drawable.bg_filter_on : R.drawable.bg_filter_off);
        tv.setTextColor(getColor(on ? R.color.white : R.color.ink));
    }

    // ---------------- 목록 ----------------
    private void setupList() {
        RecyclerView rv = findViewById(R.id.rvFound);
        GridLayoutManager glm = new GridLayoutManager(this, 2);
        rv.setLayoutManager(glm);
        adapter = new Adapter();
        rv.setAdapter(adapter);
        rv.addOnScrollListener(new RecyclerView.OnScrollListener() {
            @Override public void onScrolled(@NonNull RecyclerView r, int dx, int dy) {
                if (dy <= 0 || loading || items.size() >= total) return;
                if (glm.findLastVisibleItemPosition() >= items.size() - 4) loadPage(page + 1);
            }
        });
    }

    /** 필터가 바뀌면 처음부터 다시 */
    private void reload() {
        paintFilters();
        items.clear();
        adapter.notifyDataSetChanged();
        page = 0;
        total = 0;
        tvEmpty.setVisibility(View.GONE);
        loadPage(1);
    }

    private void loadPage(int p) {
        loading = true;
        final int seq = ++requestSeq;
        if (p == 1) progress.setVisibility(View.VISIBLE);
        String dateFrom = DATE_DAYS[dateIdx] < 0 ? null : Fmt.daysAgoIso(DATE_DAYS[dateIdx]);
        ApiClient.get(this).listFound(q, category, color, building, dateFrom, null, p, PAGE_SIZE)
                .enqueue(new ApiCallback<Models.FoundListOut>(this) {
                    @Override public void ok(Models.FoundListOut body) {
                        if (seq != requestSeq) return;
                        loading = false;
                        progress.setVisibility(View.GONE);
                        page = p;
                        total = body.total;
                        int start = items.size();
                        items.addAll(body.items);
                        adapter.notifyItemRangeInserted(start, body.items.size());
                        showCount();
                    }

                    @Override public void fail(String message) {
                        if (seq != requestSeq) return;
                        loading = false;
                        progress.setVisibility(View.GONE);
                        super.fail(message);
                    }
                });
    }

    private void showCount() {
        tvCount.setText("보관 중 " + total + "건");
        boolean filtered = q != null || category != null || color != null || building != null || dateIdx != 0;
        if (items.isEmpty()) {
            tvEmpty.setText(filtered ? "조건에 맞는 습득물이 없어요\n필터를 바꾸거나 분실 신고를 남겨 보세요"
                    : "아직 보관 중인 습득물이 없어요");
            tvEmpty.setVisibility(View.VISIBLE);
        } else {
            tvEmpty.setVisibility(View.GONE);
        }
    }

    @Override
    protected void onDestroy() {
        handler.removeCallbacks(searchLater);
        super.onDestroy();
    }

    // ---------------- 칸 하나 ----------------
    private class Adapter extends RecyclerView.Adapter<Holder> {
        @NonNull @Override
        public Holder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
            return new Holder(LayoutInflater.from(parent.getContext()).inflate(R.layout.item_found_grid, parent, false));
        }

        @Override
        public void onBindViewHolder(@NonNull Holder h, int position) {
            Models.FoundOut f = items.get(position);
            Fmt.photo(h.itemView.findViewById(R.id.ivPhoto), f.photoUrl);
            ((TextView) h.itemView.findViewById(R.id.tvTitle)).setText(f.title);
            String ago = Fmt.ago(f.foundAt);
            ((TextView) h.itemView.findViewById(R.id.tvSub)).setText(
                    f.building != null ? f.building + " · " + ago : ago);
            h.itemView.setOnClickListener(v -> FoundDetailActivity.open(FoundListActivity.this, f.id));
        }

        @Override
        public int getItemCount() { return items.size(); }
    }

    private static class Holder extends RecyclerView.ViewHolder {
        Holder(View v) { super(v); }
    }
}
