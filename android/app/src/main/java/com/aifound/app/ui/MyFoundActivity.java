package com.aifound.app.ui;

import android.os.Bundle;
import android.text.Html;
import android.view.LayoutInflater;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

import com.aifound.app.R;
import com.aifound.app.net.ApiCallback;
import com.aifound.app.net.ApiClient;
import com.aifound.app.net.Models;
import com.aifound.app.util.Fmt;
import com.aifound.app.util.TabBar;
import com.aifound.app.util.Ui;

import java.util.List;

/**
 * S24 내가 등록한 습득물 (이민서). 와이어프레임 S24_MyFound.
 * GET /me/found → 사진 · 제목 · '보관함 · 날짜' · 배지(보관 중 / 주인 확인됨 / 수령 완료). 누르면 S08.
 * 아래 '지금까지 n명에게 물건을 돌려줬어요' = GET /me/summary 의 returned_count.
 */
public class MyFoundActivity extends AppCompatActivity {

    private LinearLayout list;
    private SwipeRefreshLayout refresh;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_list_tabs);
        Ui.header(this, "내가 등록한 습득물");
        TabBar.setup(this, TabBar.MY);
        list = findViewById(R.id.list);
        refresh = findViewById(R.id.refresh);
        refresh.setOnRefreshListener(this::load);
    }

    @Override
    protected void onResume() {
        super.onResume();
        load();
    }

    private void load() {
        refresh.setRefreshing(true);
        ApiClient.get(this).myFound().enqueue(new ApiCallback<List<Models.FoundOut>>(this) {
            @Override public void ok(List<Models.FoundOut> items) {
                refresh.setRefreshing(false);
                show(items);
            }

            @Override public void fail(String message) {
                super.fail(message);
                refresh.setRefreshing(false);
            }
        });
        ApiClient.get(this).summary().enqueue(new ApiCallback<Models.Summary>(this) {
            @Override public void ok(Models.Summary s) {
                TextView footer = findViewById(R.id.tvFooter);
                footer.setText(Html.fromHtml("<b>지금까지 " + s.returnedCount + "명에게 물건을 돌려줬어요</b><br>"
                        + "주인이 수령하면 알림으로 알려드려요", Html.FROM_HTML_MODE_COMPACT));
                footer.setVisibility(View.VISIBLE);
            }
        });
    }

    private void show(List<Models.FoundOut> items) {
        list.removeAllViews();
        if (items.isEmpty()) {
            list.addView(Ui.empty(this, "아직 등록한 습득물이 없어요.\n물건을 주웠다면 홈에서 사진 한 장으로 등록해 주세요."));
            return;
        }
        LayoutInflater inf = LayoutInflater.from(this);
        for (int i = 0; i < items.size(); i++) {
            Models.FoundOut f = items.get(i);
            View row = inf.inflate(R.layout.item_found_row, list, false);
            Fmt.photo(row.findViewById(R.id.ivPhoto), f.photoUrl);
            ((TextView) row.findViewById(R.id.tvTitle)).setText(f.title);
            String where = f.locker != null ? f.locker.name + " 보관" : Fmt.place(f);
            ((TextView) row.findViewById(R.id.tvSub)).setText(where + " · " + Fmt.shortDate(f.foundAt));
            LinearLayout tags = row.findViewById(R.id.tags);
            tags.removeAllViews();
            String label = f.displayLabel != null ? f.displayLabel : "보관 중";
            tags.addView(Ui.badge(this, label, !"returned".equals(f.displayStatus)));
            row.findViewById(R.id.divider).setVisibility(i == items.size() - 1 ? View.GONE : View.VISIBLE);
            row.setOnClickListener(v -> FoundDetailActivity.open(this, f.id));
            list.addView(row);
        }
    }
}
