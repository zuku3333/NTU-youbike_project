import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')

# 設定頁面配置
st.set_page_config(
    page_title="YouBike2.0台大校園站點分析(202502-202505)",
    page_icon="💡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 標題和說明
st.title("🚲 YouBike2.0台大校園站點分析")
st.markdown("---")


# 載入並處理資料的函數
@st.cache_data
def load_and_process_data():
    """載入並處理YouBike資料"""
    try:
        # 讀取資料
        df = pd.read_csv('youbike_ntu_stations_202502_05.csv')

        # 基本資料處理
        df['datetime'] = pd.to_datetime(df['infoTime'])
        df['hour'] = df['datetime'].dt.hour

        # 計算站點統計資料
        station_stats = df.groupby(['sno', 'sna']).agg({
            'total': 'first',
            'available_rent_bikes': ['mean', 'std', 'min', 'max'],
            'available_return_bikes': ['mean', 'std', 'min', 'max'],
            'latitude': 'first',
            'longitude': 'first'
        }).round(2)

        # 簡化欄位名稱
        station_stats.columns = ['total_capacity', 'avg_rent_bikes', 'std_rent_bikes',
                                 'min_rent_bikes', 'max_rent_bikes', 'avg_return_bikes',
                                 'std_return_bikes', 'min_return_bikes', 'max_return_bikes',
                                 'latitude', 'longitude']

        # 計算各項指標
        station_stats['usage_rate'] = (
                    (station_stats['total_capacity'] - station_stats['avg_rent_bikes']) / station_stats[
                'total_capacity']).round(3)
        station_stats['rent_ease'] = (station_stats['avg_rent_bikes'] / station_stats['total_capacity']).round(3)
        station_stats['return_ease'] = (station_stats['avg_return_bikes'] / station_stats['total_capacity']).round(3)
        station_stats['rent_variation_coeff'] = (
                    station_stats['std_rent_bikes'] / station_stats['avg_rent_bikes']).fillna(0).round(3)
        station_stats['return_variation_coeff'] = (
                    station_stats['std_return_bikes'] / station_stats['avg_return_bikes']).fillna(0).round(3)
        station_stats['stability_index'] = (
                    (station_stats['rent_variation_coeff'] + station_stats['return_variation_coeff']) / 2).round(3)
        station_stats['circulation_rate'] = station_stats['stability_index']
        station_stats['efficiency'] = (station_stats['usage_rate'] * station_stats['circulation_rate']).round(3)

        # 重設索引
        station_stats = station_stats.reset_index()

        # 簡化站點名稱用於顯示
        station_stats['short_name'] = station_stats['sna'].apply(lambda x:
                                                                 x.split('_')[1][:15] + '..' if '_' in x and len(
                                                                     x.split('_')[1]) > 15
                                                                 else (x.split('_')[1] if '_' in x else x[
                                                                                                        :15] + '..' if len(
                                                                     x) > 15 else x))

        # 計算時間趨勢
        hourly_usage = df.groupby('hour').agg({
            'available_rent_bikes': 'mean',
            'available_return_bikes': 'mean'
        }).round(2)

        return station_stats, hourly_usage, df

    except FileNotFoundError:
        st.error("找不到資料檔案 'youbike_ntu_stations_202502_05.csv'，請確保檔案在正確位置。")
        return None, None, None
    except Exception as e:
        st.error(f"資料載入錯誤: {str(e)}")
        return None, None, None


# 創建分組選擇器 - 修正邊界值重複問題
def create_group_selector(data, metric, title):
    """創建資料分組選擇器 - 修正邊界值重複問題"""
    if data is None or metric not in data.columns:
        return None

    min_val = data[metric].min()
    max_val = data[metric].max()

    # 創建四分位數分組 - 使用更精確的邊界處理
    q1 = data[metric].quantile(0.25)
    q2 = data[metric].quantile(0.5)
    q3 = data[metric].quantile(0.75)

    groups = {
        f"低 ({min_val:.3f} - {q1:.3f})": (min_val, q1, 'inclusive'),
        f"中低 ({q1:.3f} - {q2:.3f})": (q1, q2, 'exclusive_left'),
        f"中高 ({q2:.3f} - {q3:.3f})": (q2, q3, 'exclusive_left'),
        f"高 ({q3:.3f} - {max_val:.3f})": (q3, max_val, 'exclusive_left')
    }

    selected_groups = st.multiselect(
        f"選擇{title}區間:",
        list(groups.keys()),
        default=list(groups.keys()),
        key=f"group_{metric}"
    )

    return groups, selected_groups


# 主要功能函數
def plot_usage_rate(station_stats):
    """站點使用率分析"""
    st.subheader("📌 站點使用率分析")

    # 詳細分析說明
    st.markdown("""
    **分析說明：**
    - **使用率公式**：使用率 = (總容量 - 平均可借車輛) / 總容量
    - **高使用率站點**：表示該站點的車輛經常被借走，是熱門的借車地點
    - **低使用率站點**：表示該站點常有車輛可借，可能位於較少人流的區域
    - **管理建議**：高使用率站點需要更頻繁的車輛調度補充
    - 🔔圖表操作說明：拖曳圖表左右移動｜使用滑桿快速跳轉｜滾輪縮放｜雙擊重置視圖
    """)

    # 創建分組選擇器
    groups, selected_groups = create_group_selector(station_stats, 'usage_rate', '使用率')

    if groups and selected_groups:
        # 根據選擇的分組過濾資料
        filtered_data = pd.DataFrame()
        colors = []

        color_map = {
            list(groups.keys())[0]: '#FFE0E6',  # 淺粉紅
            list(groups.keys())[1]: '#FFB3C1',  # 中粉紅
            list(groups.keys())[2]: '#FF8A9B',  # 深粉紅
            list(groups.keys())[3]: '#FF6B7F'   # 鮮粉紅
        }

        for group_name in groups.keys():
            min_val, max_val, boundary_type = groups[group_name]
            # 處理邊界值重複問題
            if boundary_type == 'inclusive':
                group_data = station_stats[
                    (station_stats['usage_rate'] >= min_val) &
                    (station_stats['usage_rate'] <= max_val)
                ].copy()
            else:  # exclusive_left
                group_data = station_stats[
                    (station_stats['usage_rate'] > min_val) &
                    (station_stats['usage_rate'] <= max_val)
                ].copy()

            if group_name in selected_groups:  # 只處理選中的分組
                group_data['group'] = group_name
                filtered_data = pd.concat([filtered_data, group_data])

        # 排序資料
        filtered_data = filtered_data.sort_values('usage_rate', ascending=True)

        # 創建散布圖
        # 創建散布圖 - 橫軸和縱軸對調
        fig = px.scatter(
            filtered_data,
            x='short_name',  # 改為 x 軸
            y='usage_rate',  # 改為 y 軸
            size='total_capacity',
            color='group',
            hover_data={
                'sna': True,
                'usage_rate': ':.3f',
                'total_capacity': True,
                'avg_rent_bikes': ':.1f',
                'short_name': False
            },
            title="站點使用率分佈",
            labels={'short_name': '站點名稱', 'usage_rate': '使用率'},  # 標籤對調
            color_discrete_map=color_map
        )

        # 計算合適的圖表寬度（每個站點預留更多空間）
        chart_width = max(1200, len(filtered_data) * 80)  # 每個站點80像素寬度

        # 排序資料並重新設定索引
        filtered_data = filtered_data.sort_values('usage_rate', ascending=True).reset_index(drop=True)

        selected_color_map = {group_name: color_map[group_name]
                              for group_name in selected_groups
                              if group_name in color_map}
        # 創建散布圖 - 橫軸和縱軸對調，並添加可拖曳功能
        fig = px.scatter(
            filtered_data,
            x=filtered_data.index,  # 使用索引作為 x 軸位置
            y='usage_rate',  # 改為 y 軸
            size='total_capacity',
            color='group',
            hover_data={
                'sna': True,
                'usage_rate': ':.3f',
                'total_capacity': True,
                'avg_rent_bikes': ':.1f'
            },
            title="站點使用率分佈",
            labels={'x': '站點名稱', 'usage_rate': '使用率'},
            color_discrete_map=selected_color_map  # 使用原始的 color_map
        )

        # 計算合適的圖表寬度（縮小間距）
        chart_width = max(1000, len(filtered_data) * 40)  # 每個站點40像素寬度（縮小間距）

        # 排序資料並重新設定索引
        filtered_data = filtered_data.sort_values('usage_rate', ascending=True).reset_index(drop=True)

        # 創建散布圖 - 橫軸和縱軸對調，並添加可拖曳功能
        fig = px.scatter(
            filtered_data,
            x=filtered_data.index,  # 使用索引作為 x 軸位置
            y='usage_rate',  # 改為 y 軸
            size='total_capacity',
            color='group',
            hover_data={
                'sna': True,
                'usage_rate': ':.3f',
                'total_capacity': True,
                'avg_rent_bikes': ':.1f'
            },
            title="站點使用率分佈",
            labels={'x': '站點名稱', 'usage_rate': '使用率'},
            color_discrete_map=color_map
        )

        # 計算合適的圖表寬度（縮小間距）
        chart_width = max(1000, len(filtered_data) * 40)  # 每個站點40像素寬度（縮小間距）

        fig.update_layout(
            height=700,  # 增加圖表高度給滑桿留空間
            width=chart_width,
            showlegend=True,
            legend=dict(
                orientation="h",  # 水平排列
                yanchor="bottom",
                y=1.02,  # 放在圖表上方
                xanchor="center",
                x=0.5  # 置中
            ),
            xaxis_title="站點名稱",
            yaxis_title="使用率",
            xaxis={
                'tickangle': 45,  # 傾斜45度
                'tickmode': 'array',
                'tickvals': list(range(len(filtered_data))),
                'ticktext': filtered_data['short_name'].tolist(),
                'range': [-0.5, len(filtered_data) - 0.5]  # 確保資料在軸內
            },
            yaxis={
                'range': [filtered_data['usage_rate'].min() * 0.95,
                          filtered_data['usage_rate'].max() * 1.05]  # 確保資料在軸內，留5%邊距
            },
            dragmode='pan',  # 設定為拖曳模式
            margin={'b': 150}  # 增加底部邊距給滑桿和傾斜文字留更多空間
        )

        # 設定 x 軸可拖曳範圍
        fig.update_xaxes(
            rangeslider_visible=True,  # 顯示範圍滑桿
            rangeslider_thickness=0.12,  # 增加滑桿厚度以完全包覆圓點
            rangeslider_bgcolor="rgba(0,0,0,0.1)",  # 設定滑桿背景色
            range=[0, min(20, len(filtered_data))]  # 初始顯示前20個站點
        )
        st.plotly_chart(fig, use_container_width=True)


def plot_circulation_rate(station_stats):
    """站點流動率分析"""
    st.subheader("📌 站點流動率分析")

    # 詳細分析說明
    st.markdown("""
    **分析說明：**
    - **流動率計算**：基於借車和還車的變異係數平均值
    - **借車變異係數**：反映借車數量的波動程度，數值越高表示借車需求變化越大
    - **還車變異係數**：反映還車數量的波動程度，數值越高表示還車需求變化越大
    - **高流動率站點**：使用頻繁且變化大，通常位於交通樞紐或商業區
    - **低流動率站點**：使用相對穩定，變化較小
    """)

    groups, selected_groups = create_group_selector(station_stats, 'circulation_rate', '流動率')

    if groups and selected_groups:
        filtered_data = pd.DataFrame()
        color_map = {
            list(groups.keys())[0]: '#C8E6C9',  # 淺綠色
            list(groups.keys())[1]: '#66BB6A',  # 中綠色
            list(groups.keys())[2]: '#2E7D32',  # 深綠色
            list(groups.keys())[3]: '#1B5E20'   # 深森林綠
        }

        for group_name in groups.keys():
            min_val, max_val, boundary_type = groups[group_name]
            # 修正邊界值重複問題
            if boundary_type == 'inclusive':
                group_data = station_stats[
                    (station_stats['circulation_rate'] >= min_val) &
                    (station_stats['circulation_rate'] <= max_val)
                ].copy()
            else:  # exclusive_left
                group_data = station_stats[
                    (station_stats['circulation_rate'] > min_val) &
                    (station_stats['circulation_rate'] <= max_val)
                ].copy()

            if group_name in selected_groups:  # 只加入選中的分組
                group_data['group'] = group_name
                filtered_data = pd.concat([filtered_data, group_data])

        # 改為散布圖
        fig = px.scatter(
            filtered_data,
            x='circulation_rate',
            y='total_capacity',
            size='avg_rent_bikes',
            color='group',
            hover_data={
                'sna': True,
                'circulation_rate': ':.3f',
                'rent_variation_coeff': ':.3f',
                'return_variation_coeff': ':.3f',
                'total_capacity': True,
                'avg_rent_bikes': ':.1f'
            },
            title="站點流動率vs車位數關係",
            labels={'circulation_rate': '流動率', 'total_capacity': '總車位數'},
            color_discrete_map=color_map
        )

        fig.update_layout(
            height=600,
            showlegend=True,
            xaxis_title="流動率",
            yaxis_title="總車位數"
        )

        st.plotly_chart(fig, use_container_width=True)


def plot_rent_ease(station_stats):
    """站點借車容易度分析"""
    st.subheader("📌 站點借車容易度分析")

    # 詳細分析說明
    st.markdown("""
    **借車容易度分析說明：**
    - **計算公式**：借車容易度 = 平均可借車輛數 / 總容量
    - **指標意義**：反映在該站點找到可借車輛的機率
    - **高借車容易度站點**：
      - 數值接近1.0，表示經常有車可借
      - 適合作為起點站，使用者容易取得車輛
      - 可能位於住宅區或車輛供應充足的區域
    - **低借車容易度站點**：
      - 數值接近0.0，表示經常沒車可借
      - 車輛需求大於供應，是熱門的借車地點
      - 需要加強車輛調度和補充
    - **X軸（總車位數）**：站點規模大小
    - **Y軸（借車容易度）**：找到車輛的容易程度
    - **圓點大小**：代表平均可借車輛數，圓點越大表示平均可借車輛越多
    """)

    groups, selected_groups = create_group_selector(station_stats, 'rent_ease', '借車容易度')

    if groups and selected_groups:
        filtered_data = pd.DataFrame()
        color_map = {
            list(groups.keys())[0]: 'lightcoral',
            list(groups.keys())[1]: 'coral',
            list(groups.keys())[2]: 'red',
            list(groups.keys())[3]: 'darkred'
        }

        for group_name in groups.keys():
            min_val, max_val, boundary_type = groups[group_name]
            if boundary_type == 'inclusive':
                group_data = station_stats[
                    (station_stats['rent_ease'] >= min_val) &
                    (station_stats['rent_ease'] <= max_val)
                ].copy()
            else:
                group_data = station_stats[
                    (station_stats['rent_ease'] > min_val) &
                    (station_stats['rent_ease'] <= max_val)
                ].copy()

            if group_name in selected_groups:  # 只加入選中的分組
                group_data['group'] = group_name
                filtered_data = pd.concat([filtered_data, group_data])

        fig = px.scatter(
            filtered_data,
            x='total_capacity',
            y='rent_ease',
            size='avg_rent_bikes',
            color='group',
            hover_data={
                'sna': True,
                'rent_ease': ':.3f',
                'avg_rent_bikes': ':.1f',
                'total_capacity': True
            },
            title="車位數vs借車容易度關係",
            labels={'total_capacity': '總車位數', 'rent_ease': '借車容易度'},
            color_discrete_map=color_map
        )

        fig.update_layout(height=600, showlegend=True)
        st.plotly_chart(fig, use_container_width=True)


def plot_return_ease(station_stats):
    """站點還車容易度分析"""
    st.subheader("📌 站點還車容易度分析")

    # 詳細分析說明
    st.markdown("""
    **還車容易度分析說明：**
    - **計算公式**：還車容易度 = 平均可還車位數 / 總容量
    - **指標意義**：反映在該站點找到空車位的機率
    - **高還車容易度站點**：
      - 數值接近1.0，表示經常有空位可還車
      - 適合作為目的地站，使用者容易歸還車輛
      - 可能位於辦公區或車輛需求較低的區域
    - **低還車容易度站點**：
      - 數值接近0.0，表示經常沒有空位
      - 車位需求大於供應，是熱門的還車地點
      - 需要加強車輛清運和空位管理
    - **X軸（總車位數）**：站點規模大小
    - **Y軸（還車容易度）**：找到空車位的容易程度
    - **圓點大小**：代表平均可還車位數，圓點越大表示平均空車位越多
    """)

    groups, selected_groups = create_group_selector(station_stats, 'return_ease', '還車容易度')

    if groups and selected_groups:
        filtered_data = pd.DataFrame()
        color_map = {
            list(groups.keys())[0]: 'lightyellow',
            list(groups.keys())[1]: 'yellow',
            list(groups.keys())[2]: 'orange',
            list(groups.keys())[3]: 'darkorange'
        }

        for group_name in groups.keys():
            min_val, max_val, boundary_type = groups[group_name]
            if boundary_type == 'inclusive':
                group_data = station_stats[
                    (station_stats['return_ease'] >= min_val) &
                    (station_stats['return_ease'] <= max_val)
                ].copy()
            else:
                group_data = station_stats[
                    (station_stats['return_ease'] > min_val) &
                    (station_stats['return_ease'] <= max_val)
                ].copy()

            if group_name in selected_groups:  # 只加入選中的分組
                group_data['group'] = group_name
                filtered_data = pd.concat([filtered_data, group_data])

        fig = px.scatter(
            filtered_data,
            x='total_capacity',
            y='return_ease',
            size='avg_return_bikes',
            color='group',
            hover_data={
                'sna': True,
                'return_ease': ':.3f',
                'avg_return_bikes': ':.1f',
                'total_capacity': True
            },
            title="車位數vs還車容易度關係",
            labels={'total_capacity': '總車位數', 'return_ease': '還車容易度'},
            color_discrete_map=color_map
        )

        fig.update_layout(height=600, showlegend=True)
        st.plotly_chart(fig, use_container_width=True)


def plot_stability(station_stats):
    """站點穩定度分析"""
    st.subheader("📌 站點借還車穩定度分析")

    # 詳細分析說明
    st.markdown("""
    **穩定度分析說明：**
    - **穩定度指標**：綜合考量借車和還車變異係數的平均值
    - **變異係數意義**：標準差除以平均值，用來衡量數據的相對變異程度
    - **低穩定度指標**：表示站點使用情況穩定，借還車數量變化較小，適合作為可靠的服務點
    - **高穩定度指標**：表示站點使用情況波動較大，可能受到特定時間或事件影響
    - **X軸（借車變異係數）**：反映借車需求的穩定性
    - **Y軸（還車變異係數）**：反映還車需求的穩定性
    - **圓點大小**：代表綜合穩定度指標，越大表示越不穩定
    """)

    groups, selected_groups = create_group_selector(station_stats, 'stability_index', '穩定度')

    if groups and selected_groups:
        filtered_data = pd.DataFrame()
        color_map = {
            list(groups.keys())[0]: 'lightpink',
            list(groups.keys())[1]: 'pink',
            list(groups.keys())[2]: 'hotpink',
            list(groups.keys())[3]: 'deeppink'
        }

        for group_name in groups.keys():
            min_val, max_val, boundary_type = groups[group_name]
            if boundary_type == 'inclusive':
                group_data = station_stats[
                    (station_stats['stability_index'] >= min_val) &
                    (station_stats['stability_index'] <= max_val)
                ].copy()
            else:
                group_data = station_stats[
                    (station_stats['stability_index'] > min_val) &
                    (station_stats['stability_index'] <= max_val)
                ].copy()

            if group_name in selected_groups:  # 只加入選中的分組
                group_data['group'] = group_name
                filtered_data = pd.concat([filtered_data, group_data])

        fig = px.scatter(
            filtered_data,
            x='rent_variation_coeff',
            y='return_variation_coeff',
            size='stability_index',
            color='group',
            hover_data={
                'sna': True,
                'stability_index': ':.3f',
                'rent_variation_coeff': ':.3f',
                'return_variation_coeff': ':.3f'
            },
            title="借車vs還車變異係數關係",
            labels={'rent_variation_coeff': '借車變異係數', 'return_variation_coeff': '還車變異係數'},
            color_discrete_map=color_map
        )

        fig.update_layout(height=600, showlegend=True)
        st.plotly_chart(fig, use_container_width=True)


def plot_hourly_trend(hourly_usage):
    """時間段使用趨勢分析"""
    st.subheader("⏰ 時間段使用趨勢分析")

    # 詳細分析說明
    st.markdown("""
    **時間段使用趨勢分析說明：**
    - **藍色線條（平均可借車輛）**：
      - 反映各時段車輛的供應情況
      - 數值高：表示該時段車輛較充足，使用需求相對較低
      - 數值低：表示該時段車輛較稀缺，使用需求較高
    - **紅色線條（平均可還車位）**：
      - 反映各時段車位的供應情況
      - 數值高：表示該時段空車位較多，還車需求相對較低
      - 數值低：表示該時段空車位較少，還車需求較高
    - **典型使用模式**：
      - **通勤尖峰時段**：早上7-9點和下午5-7點，借車需求高，可借車輛少
      - **離峰時段**：夜間和中午，使用需求低，車輛和車位相對充足
      - **週末模式**：使用模式可能與平日不同，較為平緩
    """)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=hourly_usage.index,
        y=hourly_usage['available_rent_bikes'],
        mode='lines+markers',
        name='平均可借車輛',
        line=dict(color='blue', width=3),
        marker=dict(size=8),
        hovertemplate='時間: %{x}:00<br>可借車輛: %{y:.1f}<extra></extra>'
    ))

    fig.add_trace(go.Scatter(
        x=hourly_usage.index,
        y=hourly_usage['available_return_bikes'],
        mode='lines+markers',
        name='平均可還車位',
        line=dict(color='red', width=3),
        marker=dict(size=8),
        hovertemplate='時間: %{x}:00<br>可還車位: %{y:.1f}<extra></extra>'
    ))

    fig.update_layout(
        title="每小時使用趨勢",
        xaxis_title="小時",
        yaxis_title="車輛/車位數",
        height=500,
        hovermode='x unified'
    )

    st.plotly_chart(fig, use_container_width=True)


def plot_capacity_circulation(station_stats):
    """車位數與流通率關係"""
    st.subheader("📌 車位數與流通率關係")

    # 詳細分析說明
    st.markdown("""
    **分析說明：**
    - **X軸（車位數）**：站點的總容量，反映站點規模大小
    - **Y軸（流通率）**：反映站點的使用頻率和變化程度
    - **圓點大小**：代表使用率，圓點越大表示使用率越高
    - **關係解讀**：
      - 大容量高流通率：大型繁忙站點，需要重點管理
      - 大容量低流通率：大型穩定站點，服務可靠
      - 小容量高流通率：小型熱點站點，可能需要擴容
      - 小容量低流通率：小型冷門站點，使用率較低
    """)

    groups, selected_groups = create_group_selector(station_stats, 'total_capacity', '車位數')

    if groups and selected_groups:
        filtered_data = pd.DataFrame()
        color_map = {
            list(groups.keys())[0]: '#FFF3CD',  # 淺黃色
            list(groups.keys())[1]: '#FFD93D',  # 金黃色
            list(groups.keys())[2]: '#FF8F00',  # 橙黃色
            list(groups.keys())[3]: '#E65100'   # 深橙色
        }

        for group_name in groups.keys():
            min_val, max_val, boundary_type = groups[group_name]
            if boundary_type == 'inclusive':
                group_data = station_stats[
                    (station_stats['total_capacity'] >= min_val) &
                    (station_stats['total_capacity'] <= max_val)
                ].copy()
            else:
                group_data = station_stats[
                    (station_stats['total_capacity'] > min_val) &
                    (station_stats['total_capacity'] <= max_val)
                ].copy()

            if group_name in selected_groups:  # 只加入選中的分組
                group_data['group'] = group_name
                filtered_data = pd.concat([filtered_data, group_data])

        fig = px.scatter(
            filtered_data,
            x='total_capacity',
            y='circulation_rate',
            size='usage_rate',
            color='group',
            hover_data={
                'sna': True,
                'total_capacity': True,
                'circulation_rate': ':.3f',
                'usage_rate': ':.3f'
            },
            title="車位數與流通率關係分析",
            labels={'total_capacity': '總車位數', 'circulation_rate': '流通率'},
            color_discrete_map=color_map
        )

        fig.update_layout(height=600, showlegend=True)
        st.plotly_chart(fig, use_container_width=True)


def plot_efficiency(station_stats):
    """站點使用效率分析"""
    st.subheader("📌 站點使用效率分析")

    # 詳細分析說明
    st.markdown("""
    **使用效率分析說明：**
    - **X軸（使用效率）**：綜合效率指標，數值越高表示站點越重要
    - **Y軸（使用率）**：車輛被借走的比例，數值越高表示需求越大
    - **圓點大小**：代表總車位數，圓點越大表示站點規模越大
    - **圓點顏色**：代表效率分組（深橙=高效率，淺橙=低效率）
    - **高效率站點特徵**：
      - 車輛利用率高（經常被借走）、使用變化頻繁（流通活躍）、是系統中的核心服務點
    - **低效率站點特徵**：
      - 車輛閒置較多或使用穩定但不活躍
    - **右上角（高效率高使用率）**：核心熱門站點，需要重點管理和維護
    - **右下角（高效率低使用率）**：活躍但閒置的站點，可能是重要的車輛供應點
    - **左上角（低效率高使用率）**：穩定繁忙的站點，使用率高但變化小
    - **左下角（低效率低使用率）**：冷門站點，使用率和活躍度都較低

    """)

    groups, selected_groups = create_group_selector(station_stats, 'efficiency', '使用效率')

    if groups and selected_groups:
        filtered_data = pd.DataFrame()
        color_map = {
            list(groups.keys())[0]: '#FFE5CC',  # 淺橙色
            list(groups.keys())[1]: '#FFCC80',  # 中橙色
            list(groups.keys())[2]: '#FFB347',  # 亮橙色
            list(groups.keys())[3]: '#FF9500'   # 鮮橙色
        }

        for group_name in groups.keys():
            min_val, max_val, boundary_type = groups[group_name]
            # 修正邊界值重複問題
            if boundary_type == 'inclusive':
                group_data = station_stats[
                    (station_stats['efficiency'] >= min_val) &
                    (station_stats['efficiency'] <= max_val)
                ].copy()
            else:  # exclusive_left
                group_data = station_stats[
                    (station_stats['efficiency'] > min_val) &
                    (station_stats['efficiency'] <= max_val)
                ].copy()

            if group_name in selected_groups:  # 只加入選中的分組
                group_data['group'] = group_name
                filtered_data = pd.concat([filtered_data, group_data])

        # 改為散布圖
        fig = px.scatter(
            filtered_data,
            x='efficiency',
            y='usage_rate',
            size='total_capacity',
            color='group',
            hover_data={
                'sna': True,
                'efficiency': ':.3f',
                'usage_rate': ':.3f',
                'circulation_rate': ':.3f',
                'total_capacity': True
            },
            title="站點使用效率vs使用率關係",
            labels={'efficiency': '使用效率', 'usage_rate': '使用率'},
            color_discrete_map=color_map
        )

        fig.update_layout(
            height=600,
            showlegend=True,
            xaxis_title="使用效率",
            yaxis_title="使用率"
        )

        st.plotly_chart(fig, use_container_width=True)


# 主應用程式
def main():
    # 載入資料
    station_stats, hourly_usage, raw_data = load_and_process_data()

    if station_stats is None:
        return

    # 側邊欄選單
    st.sidebar.header("📋 分析主題選單")

    analysis_options = {
        "站點使用率": "🗝️",
        "站點流動率": "🔄",
        "站點借車容易度": "🚲",
        "站點還車容易度": "🅿️",
        "站點穩定度": " ⚖",
        "時間段使用趨勢": "⌛",
        "車位數與流通率關係": "🚀",
        "站點使用效率": "⚡"
    }

    selected_analysis = st.sidebar.selectbox(
        "選擇分析主題:",
        list(analysis_options.keys()),
        format_func=lambda x: f"{analysis_options[x]} {x}"
    )

    # 顯示基本統計資訊
    st.sidebar.markdown("---")
    st.sidebar.subheader("🏷️ 基本統計")
    st.sidebar.metric("總站點數", len(station_stats))
    st.sidebar.metric("平均車位數", f"{station_stats['total_capacity'].mean():.1f}")
    st.sidebar.metric("平均使用率", f"{station_stats['usage_rate'].mean():.3f}")

    # 根據選擇顯示對應分析
    if selected_analysis == "站點使用率":
        plot_usage_rate(station_stats)
    elif selected_analysis == "站點流動率":
        plot_circulation_rate(station_stats)
    elif selected_analysis == "站點借車容易度":
        plot_rent_ease(station_stats)
    elif selected_analysis == "站點還車容易度":
        plot_return_ease(station_stats)
    elif selected_analysis == "站點穩定度":
        plot_stability(station_stats)
    elif selected_analysis == "時間段使用趨勢":
        plot_hourly_trend(hourly_usage)
    elif selected_analysis == "車位數與流通率關係":
        plot_capacity_circulation(station_stats)
    elif selected_analysis == "站點使用效率":
        plot_efficiency(station_stats)

    # 資料表顯示
    st.markdown("---")
    st.subheader("📎 詳細資料表")

    # 選擇要顯示的欄位
    columns_to_show = st.multiselect(
        "選擇要顯示的欄位:",
        ['sna', 'total_capacity', 'usage_rate', 'rent_ease', 'return_ease',
         'circulation_rate', 'stability_index', 'efficiency', 'avg_rent_bikes', 'avg_return_bikes'],
        default=['sna', 'total_capacity', 'usage_rate', 'efficiency']
    )

    if columns_to_show:
        st.dataframe(
            station_stats[columns_to_show].round(3),
            use_container_width=True,
            height=400
        )

    # 下載資料功能
    st.markdown("---")
    st.subheader("💾 資料下載")

    @st.cache_data
    def convert_df(df):
        return df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')

    csv = convert_df(station_stats)

    st.download_button(
        label="📥 下載完整分析結果 (CSV)",
        data=csv,
        file_name='youbike_analysis_result.csv',
        mime='text/csv',
    )


if __name__ == "__main__":
    main()
