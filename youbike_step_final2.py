import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
import numpy as np
import warnings

warnings.filterwarnings('ignore')

# 設定頁面配置
st.set_page_config(page_title="YouBike2.0 台大校園站點資訊(202502-202505)", page_icon="🧭", layout="wide")


@st.cache_data
def load_youbike_data():
    """載入 YouBike 資料"""
    try:
        df = pd.read_csv('youbike_ntu_stations_202502_05.csv.gz', compression='gzip')

        # 轉換時間格式
        df['infoTime'] = pd.to_datetime(df['infoTime'])

        # 計算使用率（避免除零錯誤）
        df['bike_usage_rate'] = np.where(df['total'] > 0,
                                         df['available_rent_bikes'] / df['total'] * 100, 0)
        df['return_availability_rate'] = np.where(df['total'] > 0,
                                                  df['available_return_bikes'] / df['total'] * 100, 0)

        return df
    except Exception as e:
        st.error(f"載入資料時發生錯誤: {e}")
        return None


def create_map_visualization(df, filter_by='available_rent_bikes', min_value=0):
    """建立地圖視覺化"""
    try:
        # 計算每個站點的平均資料
        station_stats = df.groupby(['sno', 'sna', 'latitude', 'longitude']).agg({
            'total': 'first',
            'available_rent_bikes': 'mean',
            'available_return_bikes': 'mean',
            'bike_usage_rate': 'mean',
            'return_availability_rate': 'mean'
        }).reset_index()

        # 根據篩選條件過濾站點
        filtered_stats = station_stats[station_stats[filter_by] >= min_value]

        # 建立地圖物件 (以台大為中心)
        m = folium.Map(
            location=[25.014, 121.535],
            zoom_start=15,
            tiles='OpenStreetMap'
        )

        # 添加圖例
        # 加入 Marker 群集功能
        marker_cluster = MarkerCluster().add_to(m)

        # 根據每一筆站點資料建立標記
        for _, row in filtered_stats.iterrows():
            # 根據篩選屬性決定標記顏色
            if filter_by == 'available_rent_bikes':
                value = row['available_rent_bikes']
                if value >= 10:
                    color = 'green'
                elif value >= 5:
                    color = 'orange'
                else:
                    color = 'red'
            elif filter_by == 'return_availability_rate':
                value = row['return_availability_rate']
                if value >= 70:
                    color = 'green'
                elif value >= 40:
                    color = 'orange'
                else:
                    color = 'red'
            elif filter_by == 'bike_usage_rate':
                value = row['bike_usage_rate']
                if value >= 50:
                    color = 'red'  # 高使用率用紅色
                elif value >= 25:
                    color = 'orange'
                else:
                    color = 'green'
            else:  # total
                value = row['total']
                if value >= 40:
                    color = 'green'
                elif value >= 20:
                    color = 'orange'
                else:
                    color = 'red'

            # 建立彈出視窗內容
            popup_text = f"""
            <div style="width: 300px;">
                <h4>{row['sna']}</h4>
                <hr>
                <b>總車位數:</b> {row['total']:.0f}<br>
                <b>平均可租車輛:</b> {row['available_rent_bikes']:.1f}<br>
                <b>平均可還車位:</b> {row['available_return_bikes']:.1f}<br>
                <b>車輛使用率:</b> {row['bike_usage_rate']:.1f}%<br>
                <b>還車便利性:</b> {row['return_availability_rate']:.1f}%
            </div>
            """

            # 加入標記到群集
            folium.Marker(
                location=[row['latitude'], row['longitude']],
                popup=folium.Popup(popup_text, max_width=300),
                icon=folium.Icon(color=color, icon='info-sign'),
                tooltip=f"{row['sna']}"
            ).add_to(marker_cluster)

        return m

    except Exception as e:
        st.error(f"建立地圖時發生錯誤: {e}")
        return None


def main():
    """主程式"""

    # 標題
    st.title("🚲 YouBike2.0 台大校園站點資訊(202502-202505)")
    st.markdown("---")

    # 載入資料
    with st.spinner("正在載入資料..."):
        df = load_youbike_data()

    if df is None:
        st.error("無法載入資料，請檢查檔案是否存在")
        return

    st.success(f"✅ 資料載入成功！共 {len(df):,} 筆記錄，{df['sna'].nunique()} 個站點")

    # 側邊欄控制
    st.sidebar.header("🎛️ 主選單")

    # 篩選屬性選擇
    filter_options = {
        '可租車輛數': 'available_rent_bikes',
        '還車便利性': 'return_availability_rate',
        '車輛使用率': 'bike_usage_rate',
        '總車位數': 'total'
    }

    selected_filter = st.sidebar.selectbox(
        "選擇顯示屬性",
        options=list(filter_options.keys()),
        index=0
    )

    filter_column = filter_options[selected_filter]

    # 根據選擇的屬性設定篩選範圍
    if filter_column == 'available_rent_bikes':
        min_value = st.sidebar.slider("🚲 最少可租車輛數", 0, 30, 0)
        st.sidebar.markdown("🟢 充足 (≥10輛)  \n🟠 中等 (5-9輛)  \n🔴 不足 (<5輛)")
    elif filter_column == 'return_availability_rate':
        min_value = st.sidebar.slider("🅿️ 最低還車便利性 (%)", 0, 100, 0)
        st.sidebar.markdown("🟢 便利 (≥70%)  \n🟠 普通 (40-69%)  \n🔴 不便 (<40%)")
    elif filter_column == 'bike_usage_rate':
        min_value = st.sidebar.slider("📈 最低使用率 (%)", 0, 100, 0)
        st.sidebar.markdown("🔴 熱門 (≥50%)  \n🟠 中等 (25-49%)  \n🟢 冷門 (<25%)")
    else:  # total
        min_value = st.sidebar.slider("🏢 最少總車位數", 0, 100, 0)
        st.sidebar.markdown("🟢 大型 (≥40位)  \n🟠 中型 (20-39位)  \n🔴 小型 (<20位)")

    # 站點選擇
    selected_stations = st.sidebar.multiselect(
        "🏷️ 選擇特定站點 (可選)",
        options=df['sna'].unique(),
        default=[]
    )

    # 主要內容區域
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("總站點數", df['sna'].nunique())
    with col2:
        st.metric("平均可租車輛", f"{df['available_rent_bikes'].mean():.1f}")
    with col3:
        st.metric("平均使用率", f"{df['bike_usage_rate'].mean():.1f}%")
    with col4:
        st.metric("資料截止時間", df['infoTime'].max().strftime("%m/%d %H:%M"))

    # 地圖顯示
    st.subheader(f"📍 站點分布地圖 - 依 {selected_filter} 篩選")

    # 顯示當前篩選說明
    if filter_column == 'available_rent_bikes':
        st.info(f"🔍 顯示可租車輛數 ≥ {min_value} 輛的站點")
    elif filter_column == 'return_availability_rate':
        st.info(f"🔍 顯示還車便利性 ≥ {min_value}% 的站點")
    elif filter_column == 'bike_usage_rate':
        st.info(f"🔍 顯示使用率 ≥ {min_value}% 的站點")
    else:
        st.info(f"🔍 顯示總車位數 ≥ {min_value} 位的站點")

    # 建立和顯示地圖 - 置中顯示
    with st.spinner("正在建立地圖..."):
        map_viz = create_map_visualization(df, filter_column, min_value)

    if map_viz:
        try:
            from streamlit_folium import st_folium
            # 使用 container 來置中地圖，調整為85%寬度
            with st.container():
                col1, col2, col3 = st.columns([0.075, 0.85, 0.075])
                with col2:
                    st_folium(map_viz, width=None, height=600, use_container_width=True)
        except ImportError:
            # 如果沒有 streamlit_folium，則提供下載連結
            map_html = map_viz._repr_html_()
            st.download_button(
                label="📥 下載互動式地圖 HTML",
                data=map_html,
                file_name="youbike_map.html",
                mime="text/html"
            )
            st.info("💡 請安裝 streamlit-folium 套件以直接顯示地圖：`pip install streamlit-folium`")

    # 資料摘要
    st.subheader("📌 資料摘要")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("🏆 熱門站點 Top 5")
        try:
            if filter_column == 'available_rent_bikes':
                popular_stations = df.groupby('sna')[filter_column].mean().nlargest(5)
                unit = "輛"
            elif filter_column == 'return_availability_rate':
                popular_stations = df.groupby('sna')[filter_column].mean().nlargest(5)
                unit = "%"
            elif filter_column == 'bike_usage_rate':
                popular_stations = df.groupby('sna')[filter_column].mean().nlargest(5)
                unit = "%"
            else:
                popular_stations = df.groupby('sna')[filter_column].mean().nlargest(5)
                unit = "位"

            for i, (station, value) in enumerate(popular_stations.items(), 1):
                station_name = station.replace('YouBike2.0_臺大', '').replace('YouBike2.0_', '')
                if unit == "輛" or unit == "位":
                    st.write(f"{i}. {station_name}: {round(value)} {unit}")
                else:
                    st.write(f"{i}. {station_name}: {value:.1f} {unit}")
        except Exception as e:
            st.error(f"生成熱門站點時發生錯誤: {e}")

    with col2:
        st.subheader("📈 整體統計")
        try:
            avg_rent = df['available_rent_bikes'].mean()
            avg_return = df['return_availability_rate'].mean()
            avg_usage = df['bike_usage_rate'].mean()
            total_stations = df['sna'].nunique()

            st.metric("🔖️ 平均可租車輛", f"{avg_rent:.1f} 輛")
            st.metric("🔖️ 平均還車便利性", f"{avg_return:.1f}%")
            st.metric("🔖️ 平均使用率", f"{avg_usage:.1f}%")
            st.metric("🔖️ 總站點數", f"{total_stations} 個")
        except Exception as e:
            st.error(f"生成統計資料時發生錯誤: {e}")

    with col3:
        st.subheader("⏳ 時段分析")
        try:
            # 計算每小時的總可租車輛數
            hourly_usage = df.groupby(df['infoTime'].dt.hour)['available_rent_bikes'].sum()
            avg_usage = hourly_usage.mean()

            # 定義尖峰時段：高於平均使用量20%
            peak_threshold = avg_usage * 1.2
            off_peak_threshold = avg_usage * 0.8

            # 找出尖峰和離峰時段，並按使用量排序
            peak_hours_data = hourly_usage[hourly_usage >= peak_threshold].sort_values(ascending=False)
            off_peak_hours_data = hourly_usage[hourly_usage <= off_peak_threshold].sort_values(ascending=True)

            # 轉換成時段區間並選取前兩項
            def hours_to_periods_top2(hours_series):
                if hours_series.empty:
                    return "無"

                # 取前兩個時段
                top_hours = hours_series.head(2).index.tolist()
                periods = []

                for hour in top_hours:
                    periods.append(f"{hour:02d}:00-{hour + 1:02d}:00")

                return ", ".join(periods)

            peak_periods = hours_to_periods_top2(peak_hours_data)
            off_peak_periods = hours_to_periods_top2(off_peak_hours_data)

            st.write("尖峰：高於平均20%  \n離峰：低於平均20%")
            st.write("")
            st.write(f"🕒 **尖峰時段**: {peak_periods}")
            st.write(f"🕐 **離峰時段**: {off_peak_periods}")

        except Exception as e:
            st.error(f"生成時段分析時發生錯誤: {e}")

    # 資料表格
    st.subheader("📋 站點詳細資料")

    try:
        # 根據篩選條件過濾資料表
        display_df = df.copy()

        # 計算站點平均值用於過濾
        station_avg = df.groupby('sna').agg({
            'available_rent_bikes': 'mean',
            'return_availability_rate': 'mean',
            'bike_usage_rate': 'mean',
            'total': 'first'
        }).reset_index()

        # 過濾符合條件的站點
        filtered_stations = station_avg[station_avg[filter_column] >= min_value]['sna'].tolist()

        if selected_stations:
            # 如果有選擇特定站點，顯示這些站點
            display_df = display_df[display_df['sna'].isin(selected_stations)]
            st.info(f"📋 顯示 {len(selected_stations)} 個選擇的站點資料")
        else:
            # 否則顯示符合篩選條件的站點
            display_df = display_df[display_df['sna'].isin(filtered_stations)]
            st.info(f"📋 顯示 {len(filtered_stations)} 個符合條件的站點資料 ({selected_filter} ≥ {min_value})")

        if not display_df.empty:
            # 重新排列和重命名欄位
            display_columns = {
                'sna': '站點名稱',
                'available_rent_bikes': '可租車輛',
                'available_return_bikes': '可還車位',
                'total': '總車位',
                'bike_usage_rate': '使用率(%)',
                'return_availability_rate': '還車便利性(%)',
                'infoTime': '更新時間'
            }

            display_df_renamed = display_df[list(display_columns.keys())].rename(columns=display_columns)

            # 格式化數值
            display_df_renamed['使用率(%)'] = display_df_renamed['使用率(%)'].round(1)
            display_df_renamed['還車便利性(%)'] = display_df_renamed['還車便利性(%)'].round(1)

            st.dataframe(
                display_df_renamed,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("⚠️ 沒有符合篩選條件的資料")

    except Exception as e:
        st.error(f"生成資料表格時發生錯誤: {e}")


if __name__ == "__main__":
    main()
