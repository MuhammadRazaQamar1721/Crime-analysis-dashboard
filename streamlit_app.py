import streamlit as st
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import folium
from folium.plugins import MarkerCluster
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.ensemble import RandomForestClassifier
from io import BytesIO
import zipfile
import os

# Set wide layout
st.set_page_config(layout="wide")

# Loading Data Function (It auto-load from data folder)
def load_data():
    # Attempting to load local ZIP containing the CSV
    zip_path = os.path.join('data', 'humberside-street-merged.zip')
    if os.path.exists(zip_path):
        with zipfile.ZipFile(zip_path, 'r') as zf:
            csvs = [f for f in zf.namelist() if f.lower().endswith('.csv')]
            if not csvs:
                st.error("No CSV file found inside data/humberside-street-merged.zip.")
                st.stop()
            with zf.open(csvs[0]) as f:
                df = pd.read_csv(f)
    else:
        st.error("Data archive not found in data/. Please add humberside-street-merged.zip.")
        st.stop()

    # Cleaning and preprocessing
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
    df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
    df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
    df['location'] = df['location'].astype(str).str.strip()
    df = df.dropna(subset=['crime_id', 'crime_type', 'latitude', 'longitude'])
    df = df.drop_duplicates(subset=['crime_id']).reset_index(drop=True)
    return df

# Prediction model preparation\@st.cache_data
def train_model(df):
    df_model = df.dropna(subset=['lsoa_code', 'lsoa_name']).copy()
    rare = df_model['crime_type'].value_counts()[df_model['crime_type'].value_counts() < 1000].index
    df_model['crime_type'] = df_model['crime_type'].apply(lambda x: 'Other' if x in rare else x)
    features = ['longitude', 'latitude', 'reported_by', 'falls_within', 'last_outcome_category']
    X = df_model[features]
    y = df_model['crime_type']
    # Encode
    X_enc = X.copy()
    label_encoders = {}
    for col in ['reported_by', 'falls_within', 'last_outcome_category']:
        le = LabelEncoder()
        X_enc[col] = le.fit_transform(X_enc[col])
        label_encoders[col] = le
    scaler = StandardScaler()
    X_enc[['longitude', 'latitude']] = scaler.fit_transform(X_enc[['longitude', 'latitude']])
    le_target = LabelEncoder()
    y_enc = le_target.fit_transform(y)
    rf = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')
    rf.fit(X_enc, y_enc)
    return rf, le_target, scaler, label_encoders, X, df_model

# Main App
def main():
    df = load_data()

    # Creating my crime app Tabs
    tab1, tab2, tab3 = st.tabs(["General Overview", "EDA Analysis", "Crime Prediction"])

    # ===== Tab 1: General Overview =====
    with tab1:
        st.header("🔎 Predictive Analytics Dashboard for Humberside Street")
        description1 = """
        This dashboard analyses the Humberside street crime dataset (May 2022 - Apr 2025), showing:
        1. Data Overview
        2. Correlation Heatmap
        3. Interactive Crime Map (focused on Humberside area)
        """
        st.markdown(f"<div style='text-align: justify;'>{description1}</div>", unsafe_allow_html=True)
        st.subheader("1. Data Overview")
        st.write(df.head())

        st.subheader("2. Correlation Heatmap")
        description2 = """
        This heatmap is to showcase the correlations between the different variables of the data set like crime type, last outcome, and map location of crime.
            """
        st.markdown(f"<div style='text-align: justify;'>{description2}</div>", unsafe_allow_html=True)
        corr_df = pd.concat([
            df[['latitude', 'longitude']],
            pd.get_dummies(df['crime_type'], prefix='crime'),
            pd.get_dummies(df['last_outcome_category'], prefix='outcome')
        ], axis=1)
        fig, ax = plt.subplots(figsize=(10, 8))
        sns.heatmap(corr_df.corr(), center=0, cbar_kws={'shrink': .5}, ax=ax)
        ax.set_title("Correlation Matrix")
        st.pyplot(fig)

        st.subheader("3. Interactive Crime Map (Humberside Area)")
        description3 = """
           This map showcases the location of crime near to 1.0 degrees of Humberside center. Come on interact with it and find out all the trends related to Humberside crimes.
            """
        st.markdown(f"<div style='text-align: justify;'>{description3}</div>", unsafe_allow_html=True)
        # Filter to within ~1.0 degrees of Humberside center
        center_lat, center_lon = 53.5, -1.1
        df_map = df[(df['latitude'].between(center_lat-1.0, center_lat+1.0)) &
                    (df['longitude'].between(center_lon-1.0, center_lon+1.0))]
        # Sample to max 100000 points for performance
        df_sample = df_map.sample(n=min(len(df_map), 100000), random_state=42)

        m = folium.Map(location=[center_lat, center_lon], zoom_start=10)
        marker_cluster = MarkerCluster().add_to(m)
        for _, row in df_sample.iterrows():
            folium.CircleMarker(
                location=[row['latitude'], row['longitude']],
                radius=3,
                color='red',
                fill=True,
                fill_opacity=0.6
            ).add_to(marker_cluster)
        # Rendering the map directly
        map_html = m._repr_html_()
        st.components.v1.html(map_html, height=600)

    # ===== Tab 2: EDA Analysis =====
    with tab2:
        st.header("📊 Exploratory Data Analysis")
        description4 = """
        This part shows all the major plots for the crime data set. The major jurisdiction for which this data set belongs to including crime types, and last results of criminals. Both frequency and percentages are shown to highlight all major crime types in Humberside. In addition you will also find major LSOA names.
            """
        st.markdown(f"<div style='text-align: justify;'>{description4}</div>", unsafe_allow_html=True)
        cat_cols = ['falls_within', 'crime_type', 'last_outcome_category']
        for col in cat_cols:
            st.subheader(f"Count Plot: {col}")
            description5 = """
                            The following plots shows frequency and percentage of data inputs. It includes falls within variables, crime types, and, last outcome of criminal. Falls within explains the jurisdiction under which all the crime falls under. Crime types explains the type of crime particular entry represents. Finally the last outcome explains the punishment received by the criminal.
            """
            st.markdown(f"<div style='text-align: justify;'>{description5}</div>", unsafe_allow_html=True)
            counts = df[col].value_counts()
            fig, ax = plt.subplots()
            sns.barplot(y=counts.index, x=counts.values, ax=ax)
            ax.set_title(f"Counts of {col}")
            st.pyplot(fig)

            st.subheader(f"Percentage Plot: {col}")
            pct = df[col].value_counts(normalize=True) * 100
            fig, ax = plt.subplots()
            sns.barplot(y=pct.index, x=pct.values, ax=ax)
            ax.set_title(f"Percentage of {col}")
            st.pyplot(fig)

        st.subheader("Top 10 LSOA Names + 'Other'")
        description6 = """
           It's a geographical unit used in England and Wales for statistical purposes. It is particularly for analysing and mapping crime data. LSOAs are smaller than wards and designed to be relatively consistent in population size. They are typically with around 1,500 residents or 650 households
            """
        st.markdown(f"<div style='text-align: justify;'>{description6}</div>", unsafe_allow_html=True)
        
        lsoa_counts = df['lsoa_name'].value_counts()
        top10 = lsoa_counts.iloc[:10]
        top10['Other'] = lsoa_counts.iloc[10:].sum()
        fig, ax = plt.subplots()
        sns.barplot(y=top10.index, x=top10.values, ax=ax)
        ax.set_title("Top 10 LSOA Names")
        st.pyplot(fig)

    # ===== Tab 3: Crime Prediction tab =====
    with tab3:
        st.header("🔮 Crime Prediction (Next 6 Months)")
        description7 = """
          This is the last page folks for this dashboard on Humberside Crime data analysis. Hope you enjoyed it and found new patterns and trends. In this part the crime prediction results are visualised based on the past data of Humberside Crime profile.
            """
        st.markdown(f"<div style='text-align: justify;'>{description7}</div>", unsafe_allow_html=True)
        rf, le_target, scaler, label_encoders, X_train, df_model = train_model(df)

        lon_min, lon_max = df_model['longitude'].min(), df_model['longitude'].max()
        lat_min, lat_max = df_model['latitude'].min(), df_model['latitude'].max()
        future_list = []
        for m in range(1, 7):
            random_lons = np.random.uniform(lon_min, lon_max, 5000)
            random_lats = np.random.uniform(lat_min, lat_max, 5000)
            df_f = pd.DataFrame({
                'longitude': random_lons,
                'latitude': random_lats,
                'reported_by': label_encoders['reported_by'].transform([df_model['reported_by'].mode()[0]]*5000),
                'falls_within': label_encoders['falls_within'].transform([df_model['falls_within'].mode()[0]]*5000),
                'last_outcome_category': label_encoders['last_outcome_category'].transform([df_model['last_outcome_category'].mode()[0]]*5000),
                'simulated_month': m
            })
            df_f[['longitude', 'latitude']] = scaler.transform(df_f[['longitude', 'latitude']])
            preds = rf.predict(df_f[X_train.columns])
            df_f['predicted_crime_type'] = le_target.inverse_transform(preds)
            future_list.append(df_f)
        fut_df = pd.concat(future_list, ignore_index=True)

        st.subheader("Predicted Crime Types")
        description8 = """
        It shows you the crime types that are expected to continue on large in Humberside. You can easily find the major crime types below.
            """
        st.markdown(f"<div style='text-align: justify;'>{description8}</div>", unsafe_allow_html=True)
        fig, ax = plt.subplots(figsize=(8, 6))
        sns.countplot(
            data=fut_df,
            y='predicted_crime_type',
            order=fut_df['predicted_crime_type'].value_counts().index,
            ax=ax
        )
        ax.set_title("Predicted Crimes Next 6 Months")
        st.pyplot(fig)

        st.subheader("Predictions by Month")
        description9 = """
           This shows the crime profile prediction for the next half year in Humberside. Worry not police are out there guarding you 24/7.
            """
        st.markdown(f"<div style='text-align: justify;'>{description9}</div>", unsafe_allow_html=True)
        pivot = fut_df.groupby(['simulated_month', 'predicted_crime_type']).size().unstack(fill_value=0)
        fig, ax = plt.subplots(figsize=(10, 6))
        pivot.plot(kind='bar', stacked=True, ax=ax)
        ax.set_title("Predicted Crime Types by Month")
        st.pyplot(fig)

        st.subheader("Future vs Historical")
        description10 = """
          This plot shows a clear comparison between the crime rates of future prediction and historical till now.
            """
        st.markdown(f"<div style='text-align: justify;'>{description10}</div>", unsafe_allow_html=True)
        num_hist = df_model.shape[0] / 36
        future_tot = fut_df.groupby('simulated_month').size().reset_index(name='future_count')
        future_tot['historical_avg'] = num_hist
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(future_tot['simulated_month'], future_tot['future_count'], marker='o', label='Future')
        ax.plot(future_tot['simulated_month'], future_tot['historical_avg'], linestyle='--', label='Historical Avg')
        ax.set_xlabel("Month")
        ax.set_ylabel("Total Crimes")
        ax.set_title("Future Predictions vs Historical Average")
        ax.legend()
        st.pyplot(fig)

    # Download cleaned data in sidebar
    st.sidebar.header("Download Cleaned Data CSV")
    csv_data = df_model.to_csv(index=False).encode()
    st.sidebar.download_button(label="Download CSV", data=csv_data, file_name='cleaned_data.csv')

if __name__ == '__main__':
    main()





