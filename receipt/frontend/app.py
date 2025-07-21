import streamlit as st
import requests
import pandas as pd
import altair as alt

BACKEND_URL = 'http://localhost:8000'

st.title('Receipt & Bill Analyzer')

# --- OCR Language Selection ---
ocr_lang = st.text_input('OCR Language (EasyOCR, e.g., en, hi, fr, etc.)', value='en')

# --- Upload Section ---
st.header('Upload Receipt/Bill')
uploaded_file = st.file_uploader('Choose a file (.jpg, .png, .pdf, .txt)', type=['jpg', 'jpeg', 'png', 'pdf', 'txt'])
if uploaded_file:
    if st.button('Upload'):
        files = {'file': (uploaded_file.name, uploaded_file, uploaded_file.type)}
        data = {'lang': ocr_lang}
        with st.spinner('Uploading and processing...'):
            try:
                res = requests.post(f'{BACKEND_URL}/upload/', files=files, data=data, timeout=120)
                if res.ok:
                    st.success(f"Uploaded: {uploaded_file.name}")
                    st.json(res.json())
                else:
                    st.error(res.text)
            except Exception as e:
                st.error(f'Upload failed: {e}')

# --- Receipts Table with Edit ---
st.header('Receipts Table')
search = st.text_input('Search (vendor/category/filename)')
sort_by = st.selectbox('Sort by', ['', 'amount', 'date', 'vendor', 'category', 'currency'])
order = st.radio('Order', ['asc', 'desc'])
category = st.text_input('Category filter (optional)')
currency = st.text_input('Currency filter (optional, e.g., USD, INR)')
page = st.number_input('Page', min_value=1, value=1)
page_size = st.number_input('Page size', min_value=1, max_value=100, value=20)
receipts_params = {'search': search, 'sort_by': sort_by, 'order': order, 'category': category, 'currency': currency, 'page': page, 'page_size': page_size}

if st.button('Fetch Receipts'):
    with st.spinner('Fetching receipts...'):
        try:
            res = requests.get(f'{BACKEND_URL}/receipts/', params=receipts_params, timeout=30)
            if res.ok:
                df = pd.DataFrame(res.json())
                if not df.empty:
                    st.dataframe(df)
                    # Edit functionality
                    edit_row = st.number_input('Row to edit (index)', min_value=0, max_value=len(df)-1, step=1)
                    if st.button('Edit Selected Row'):
                        row = df.iloc[edit_row]
                        with st.form('edit_form'):
                            new_vendor = st.text_input('Vendor', value=row['vendor'])
                            new_date = st.text_input('Date', value=row['date'])
                            new_amount = st.number_input('Amount', value=row['amount'])
                            new_category = st.text_input('Category', value=row['category'])
                            new_currency = st.text_input('Currency', value=row['currency'])
                            submitted = st.form_submit_button('Submit Edit')
                            if submitted:
                                patch_data = {
                                    'vendor': new_vendor,
                                    'date': new_date,
                                    'amount': new_amount,
                                    'category': new_category,
                                    'currency': new_currency
                                }
                                try:
                                    patch_res = requests.patch(f'{BACKEND_URL}/receipts/{row["id"]}/', json=patch_data, timeout=30)
                                    if patch_res.ok:
                                        st.success('Receipt updated! Refresh to see changes.')
                                    else:
                                        st.error('Update failed.')
                                except Exception as e:
                                    st.error(f'Update failed: {e}')
                    # Export buttons (as before)
                    export_format = st.selectbox('Export format', ['csv', 'json'])
                    if st.button('Export filtered data'):
                        try:
                            export_res = requests.get(f'{BACKEND_URL}/receipts/export/', params={**receipts_params, 'format': export_format}, timeout=60)
                            if export_res.ok:
                                if export_format == 'csv':
                                    st.download_button('Download CSV', export_res.content, 'receipts.csv', 'text/csv')
                                else:
                                    st.download_button('Download JSON', export_res.text, 'receipts.json', 'application/json')
                            else:
                                st.error('Export failed.')
                        except Exception as e:
                            st.error(f'Export failed: {e}')
                else:
                    st.info('No receipts found.')
            else:
                st.error('Failed to fetch receipts.')
        except Exception as e:
            st.error(f'Failed to fetch receipts: {e}')

# --- Pie Chart for Category Spend ---
st.header('Category Spend (Pie Chart)')
if st.button('Fetch Statistics'):
    with st.spinner('Fetching statistics...'):
        try:
            agg_res = requests.get(f'{BACKEND_URL}/receipts/aggregate/', timeout=30)
            if agg_res.ok:
                agg = agg_res.json()
                if 'vendor_frequency' in agg and agg['vendor_frequency']:
                    freq_df = pd.DataFrame(list(agg['vendor_frequency'].items()), columns=['Vendor', 'Count'])
                    st.bar_chart(freq_df.set_index('Vendor'))
                if 'monthly_spend' in agg and agg['monthly_spend']:
                    ms_df = pd.DataFrame(list(agg['monthly_spend'].items()), columns=['Month', 'Spend'])
                    ms_df['Month'] = pd.to_datetime(ms_df['Month'])
                    ms_df = ms_df.sort_values('Month')
                    chart = alt.Chart(ms_df).mark_line(point=True).encode(
                        x='Month:T', y='Spend:Q'
                    )
                    st.altair_chart(chart, use_container_width=True)
                # Pie chart for category spend
                if 'category_spend' in agg and agg['category_spend']:
                    cat_df = pd.DataFrame(list(agg['category_spend'].items()), columns=['Category', 'Spend'])
                    st.write('Category Spend')
                    st.altair_chart(alt.Chart(cat_df).mark_arc().encode(
                        theta='Spend:Q', color='Category:N', tooltip=['Category', 'Spend']
                    ), use_container_width=True)
            else:
                st.error('Failed to fetch statistics.')
        except Exception as e:
            st.error(f'Failed to fetch statistics: {e}') 