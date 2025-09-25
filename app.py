import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, date
import threading
import queue
import time
from parser import BankiRuParser

# Настройка страницы
st.set_page_config(
    page_title="Банки.ру - Парсер отзывов",
    page_icon="🏦",
    layout="wide"
)

# Инициализация session state
if 'parsing_status' not in st.session_state:
    st.session_state.parsing_status = "idle"
if 'progress_queue' not in st.session_state:
    st.session_state.progress_queue = queue.Queue()
if 'parsed_reviews' not in st.session_state:
    st.session_state.parsed_reviews = []

def parse_reviews_thread(parser, config, progress_queue):
    """Функция для парсинга отзывов в отдельном потоке"""
    try:
        progress_queue.put(("status", "Инициализация парсера..."))
        
        reviews = parser.parse_reviews(
            start_page=config['start_page'],
            end_page=config['end_page'],
            delay_min=config['delay_min'],
            delay_max=config['delay_max'],
            jitter=config['jitter'],
            start_date=config['start_date'],
            end_date=config['end_date'],
            save_every_n_pages=config['save_every_pages'],
            get_full_text=config['get_full_text'],
            save_all_reviews=config['save_all_reviews'],
            antiban_mode=config['antiban_mode']
        )
        
        progress_queue.put(("complete", reviews))
        
    except Exception as e:
        progress_queue.put(("error", str(e)))

def main():
    st.title("🏦 Парсер отзывов Банки.ру")
    st.subheader("Парсинг отзывов о Газпромбанке")
    
    # Боковая панель с настройками
    with st.sidebar:
        st.header("⚙️ Настройки парсинга")
        
        # Диапазон страниц
        st.subheader("📄 Страницы")
        col1, col2 = st.columns(2)
        with col1:
            start_page = st.number_input("Начальная страница", min_value=1, value=1, step=1)
        with col2:
            end_page = st.number_input("Конечная страница", min_value=1, value=5, step=1)
        
        if start_page > end_page:
            st.error("Начальная страница не может быть больше конечной!")
        
        # Задержки между запросами
        st.subheader("⏱️ Тайминги")
        delay_min = st.slider("Минимальная задержка (сек)", 2.0, 20.0, 5.0, 0.5)
        delay_max = st.slider("Максимальная задержка (сек)", delay_min, 40.0, 12.0, 0.5)
        jitter = st.slider("Джиттер (сек)", 0.0, 8.0, 3.0, 0.1)
        
        # Фильтрация по датам
        st.subheader("📅 Фильтр по датам")
        use_date_filter = st.checkbox("Включить фильтр по датам")
        
        start_date_str = None
        end_date_str = None
        
        if use_date_filter:
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input(
                    "Начальная дата",
                    value=date(2023, 1, 1),
                    help="Формат: DD.MM.YYYY"
                )
                start_date_str = start_date.strftime("%d.%m.%Y")
            
            with col2:
                end_date = st.date_input(
                    "Конечная дата",
                    value=date.today(),
                    help="Формат: DD.MM.YYYY"
                )
                end_date_str = end_date.strftime("%d.%m.%Y")
            
            if start_date > end_date:
                st.error("Начальная дата не может быть больше конечной!")
        
        # Настройки сохранения
        st.subheader("💾 Сохранение")
        save_every_pages = st.number_input(
            "Сохранять каждые N страниц", 
            min_value=1, 
            value=5, 
            step=1,
            help="Создавать отдельный файл каждые N страниц"
        )
        
        save_all_reviews = st.checkbox(
            "Сохранять общий файл all_reviews",
            value=True,
            help="Создает один большой файл со всеми отзывами. Отключите для экономии места при больших объемах."
        )
        
        # Настройки парсинга
        st.subheader("🔍 Качество парсинга")
        get_full_text = st.checkbox(
            "Получать полные тексты отзывов",
            value=True,
            help="Если включено, парсер будет переходить на страницу каждого отзыва для получения полного текста. Медленнее, но полнее."
        )
        
        # Антибан настройки
        st.subheader("🛡️ Защита от блокировки")
        antiban_mode = st.checkbox(
            "Антибан режим",
            value=False,
            help="Увеличенные задержки и дополнительные меры защиты от блокировки IP"
        )
        
        if antiban_mode:
            st.warning("⚠️ В антибан режиме парсинг будет в 2-3 раза медленнее, но значительно безопаснее")
            st.info("🛡️ Включает: ротацию User-Agent, увеличенные задержки, дополнительные заголовки")
        
        if get_full_text:
            if not antiban_mode:
                st.warning("⚠️ Получение полных текстов ЗНАЧИТЕЛЬНО увеличивает время парсинга и нагрузку на сервер.")
            st.info("🕐 При включенной опции добавляется задержка 0.5-1.5 сек между каждым отзывом + основные задержки между страницами.")
            
            estimated_time = (end_page - start_page + 1) * 25 * 1.0  # примерно 25 отзывов на странице * 1 сек задержки
            if antiban_mode:
                estimated_time *= 2.5  # увеличиваем оценку времени для антибан режима
            st.info(f"⏱️ Примерное время парсинга: {estimated_time/60:.1f} минут для {end_page - start_page + 1} страниц")
        
        st.markdown("---")
        
        # Информация о настройках
        st.subheader("📊 Текущие настройки")
        st.write(f"**Страницы:** {start_page} - {end_page}")
        st.write(f"**Задержка:** {delay_min}-{delay_max} сек (±{jitter})")
        if use_date_filter:
            st.write(f"**Период:** {start_date_str} - {end_date_str}")
        st.write(f"**Сохранение:** каждые {save_every_pages} стр.")
        st.write(f"**Общий файл:** {'✅' if save_all_reviews else '❌'}")
        st.write(f"**Полные тексты:** {'✅' if get_full_text else '❌'}")
        st.write(f"**Антибан режим:** {'🛡️ ВКЛ' if antiban_mode else '❌ ВЫКЛ'}")
        
        if antiban_mode:
            st.markdown("**🛡️ Активные защиты:**")
            st.markdown("- 🔄 Ротация User-Agent")
            st.markdown("- ⏱️ Увеличенные задержки")
            st.markdown("- 🔗 Реферер заголовки")
            st.markdown("- 🛡️ Защитные заголовки")
    
    # Основная область
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.subheader("🚀 Управление парсингом")
    
    with col2:
        if st.session_state.parsing_status == "idle":
            if st.button("▶️ Начать парсинг", type="primary", use_container_width=True):
                if start_page <= end_page and (not use_date_filter or start_date <= end_date):
                    # Подготовка конфигурации
                    config = {
                        'start_page': start_page,
                        'end_page': end_page,
                        'delay_min': delay_min,
                        'delay_max': delay_max,
                        'jitter': jitter,
                        'start_date': start_date_str if use_date_filter else None,
                        'end_date': end_date_str if use_date_filter else None,
                        'save_every_pages': save_every_pages,
                        'get_full_text': get_full_text,
                        'save_all_reviews': save_all_reviews,
                        'antiban_mode': antiban_mode
                    }
                    
                    # Запуск парсинга в отдельном потоке
                    st.session_state.parsing_status = "running"
                    parser = BankiRuParser()
                    
                    thread = threading.Thread(
                        target=parse_reviews_thread,
                        args=(parser, config, st.session_state.progress_queue)
                    )
                    thread.daemon = True
                    thread.start()
                    
                    st.rerun()
        
        elif st.session_state.parsing_status == "running":
            if st.button("⏸️ Остановить", type="secondary", use_container_width=True):
                st.session_state.parsing_status = "idle"
                st.rerun()
    
    # Область прогресса
    if st.session_state.parsing_status == "running":
        st.subheader("📈 Прогресс парсинга")
        
        progress_container = st.container()
        status_container = st.container()
        
        # Проверка обновлений из очереди
        try:
            while not st.session_state.progress_queue.empty():
                message_type, data = st.session_state.progress_queue.get_nowait()
                
                if message_type == "status":
                    status_container.info(data)
                
                elif message_type == "complete":
                    st.session_state.parsed_reviews = data
                    st.session_state.parsing_status = "completed"
                    st.success(f"✅ Парсинг завершен! Найдено {len(data)} отзывов")
                    st.rerun()
                
                elif message_type == "error":
                    st.session_state.parsing_status = "error"
                    st.error(f"❌ Ошибка при парсинге: {data}")
                    st.rerun()
        
        except queue.Empty:
            pass
        
        # Анимация загрузки
        with progress_container:
            st.write("🔄 Выполняется парсинг...")
            st.progress(0.5)  # Неопределенный прогресс
        
        # Автообновление каждые 2 секунды
        time.sleep(2)
        st.rerun()
    
    # Отображение результатов
    if st.session_state.parsing_status == "completed" and st.session_state.parsed_reviews:
        st.subheader("📋 Результаты парсинга")
        
        reviews = st.session_state.parsed_reviews
        
        # Статистика
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Всего отзывов", len(reviews))
        with col2:
            reviews_with_rating = [r for r in reviews if r.get('rating')]
            st.metric("С оценкой", len(reviews_with_rating))
        with col3:
            if reviews_with_rating:
                avg_rating = sum(r['rating'] for r in reviews_with_rating) / len(reviews_with_rating)
                st.metric("Средняя оценка", f"{avg_rating:.1f}")
            else:
                st.metric("Средняя оценка", "N/A")
        with col4:
            reviews_with_date = [r for r in reviews if r.get('date')]
            st.metric("С датой", len(reviews_with_date))
        
        # Таблица отзывов
        if reviews:
            df = pd.DataFrame(reviews)
            
            # Настройка отображения колонок
            columns_to_show = ['date', 'title', 'rating', 'review_id']
            available_columns = [col for col in columns_to_show if col in df.columns]
            
            if available_columns:
                st.dataframe(
                    df[available_columns],
                    use_container_width=True,
                    hide_index=True
                )
            
            # Детальный просмотр отзыва
            st.subheader("🔍 Детальный просмотр")
            selected_idx = st.selectbox(
                "Выберите отзыв для просмотра:",
                range(len(reviews)),
                format_func=lambda x: f"{x+1}. {reviews[x].get('title', 'Без заголовка')[:50]}..."
            )
            
            if selected_idx is not None:
                review = reviews[selected_idx]
                
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write(f"**Заголовок:** {review.get('title', 'N/A')}")
                    st.write(f"**Дата:** {review.get('date', 'N/A')}")
                    st.write(f"**URL:** {review.get('url', 'N/A')}")
                    st.write(f"**ID отзыва:** {review.get('review_id', 'N/A')}")
                
                with col2:
                    rating = review.get('rating')
                    if rating:
                        st.metric("Оценка", f"{rating}/5", delta=None)
                    else:
                        st.metric("Оценка", "N/A")
                
                if review.get('text'):
                    st.write("**Текст отзыва:**")
                    st.text_area("", review['text'], height=150, disabled=True)
    
    # Файловый менеджер
    st.subheader("📁 Сохраненные файлы")
    
    if os.path.exists("out"):
        files = [f for f in os.listdir("out") if f.endswith(".json")]
        if files:
            files.sort()
            
            col1, col2 = st.columns([3, 1])
            with col1:
                selected_file = st.selectbox("Выберите файл для просмотра:", files)
            
            with col2:
                if st.button("📥 Загрузить файл"):
                    file_path = os.path.join("out", selected_file)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_data = f.read()
                    
                    st.download_button(
                        label="💾 Скачать JSON",
                        data=file_data,
                        file_name=selected_file,
                        mime="application/json"
                    )
            
            if selected_file:
                try:
                    with open(os.path.join("out", selected_file), 'r', encoding='utf-8') as f:
                        file_reviews = json.load(f)
                    
                    st.write(f"**Файл:** {selected_file}")
                    st.write(f"**Количество отзывов:** {len(file_reviews)}")
                    
                    if file_reviews:
                        df_file = pd.DataFrame(file_reviews)
                        st.dataframe(df_file.head(10), use_container_width=True)
                
                except Exception as e:
                    st.error(f"Ошибка при чтении файла: {e}")
        else:
            st.info("📂 Нет сохраненных файлов")
    else:
        st.info("📂 Папка 'out' не найдена")

if __name__ == "__main__":
    main()