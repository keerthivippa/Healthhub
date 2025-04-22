import streamlit as st
import os
import logging
from dotenv import load_dotenv
import nltk
import re
from geopy.geocoders import Nominatim
from PIL import Image
import io
import requests
from datetime import datetime
import urllib.parse
import folium
from streamlit_folium import st_folium
import time
from random import randint

# Download required NLTK data
nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True)
nltk.download('averaged_perceptron_tagger', quiet=True)
nltk.download('maxent_ne_chunker', quiet=True)
nltk.download('words', quiet=True)

# Load environment variables
load_dotenv()

# Tokens and IDs
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

# Configure logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

def send_emergency_alert_to_admin(emergency_details, uploaded_files):
    """Send emergency details and images to admin chat"""
    try:
        base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
        
        alert_message = (
            "🚨 NEW EMERGENCY ALERT 🚨\n\n"
            f"Type: {emergency_details['type']}\n"
            f"Time: {emergency_details['time']}\n\n"
        )

        # Handle location information
        if emergency_details.get('current_location'):
            try:
                # Parse location string to get coordinates
                if isinstance(emergency_details['current_location'], str):
                    lat, lon = map(float, emergency_details['current_location'].split(','))
                else:
                    lat = emergency_details['current_location'].get('latitude')
                    lon = emergency_details['current_location'].get('longitude')

                # Create Google Maps link
                maps_link = f"https://www.google.com/maps?q={lat},{lon}"
                
                # Add location information to message
                alert_message += (
                    f"📍 Location Coordinates: {lat}, {lon}\n"
                    f"🗺️ Google Maps: {maps_link}\n"
                )

                # Try to get address from coordinates using Nominatim
                try:
                    geolocator = Nominatim(user_agent="emergency_app")
                    location = geolocator.reverse(f"{lat}, {lon}")
                    if location and location.address:
                        alert_message += f"📌 Reverse Geocoded Address: {location.address}\n"
                except Exception as geo_error:
                    logger.error(f"Geocoding error: {geo_error}")
                    
            except Exception as loc_error:
                logger.error(f"Location parsing error: {loc_error}")
                alert_message += f"📍 Location (raw): {emergency_details['current_location']}\n"

        if emergency_details.get('text_address'):
            alert_message += f"🏠 Provided Address: {emergency_details['text_address']}\n"
            # Try to get coordinates for the text address
            try:
                geolocator = Nominatim(user_agent="emergency_app")
                location = geolocator.geocode(emergency_details['text_address'])
                if location:
                    maps_link = f"https://www.google.com/maps?q={location.latitude},{location.longitude}"
                    alert_message += f"🗺️ Address Google Maps: {maps_link}\n"
            except Exception as geo_error:
                logger.error(f"Address geocoding error: {geo_error}")

        # Send text message
        message_data = {
            "chat_id": ADMIN_CHAT_ID,
            "text": alert_message,
            "parse_mode": "HTML"
        }
        requests.post(f"{base_url}/sendMessage", json=message_data)

        # Send photos if any
        if uploaded_files:
            for file in uploaded_files:
                files = {"photo": file.getvalue()}
                photo_data = {
                    "chat_id": ADMIN_CHAT_ID,
                    "caption": "Emergency situation photo"
                }
                requests.post(f"{base_url}/sendPhoto", data=photo_data, files=files)

        return True
    except Exception as e:
        logger.error(f"Failed to send emergency alert: {e}")
        return False

def custom_card(title, content=None, color="#FF4B4B", icon=None):
    """Enhanced card component with optional icon"""
    icon_html = f"<span style='font-size: 24px; margin-right: 10px;'>{icon}</span>" if icon else ""
    st.markdown(
        f"""
        <div style="
            padding: 20px;
            border-radius: 10px;
            margin: 10px 0;
            background-color: #1E1E1E;
            border-left: 5px solid {color};
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);">
            <div style="display: flex; align-items: center;">
                {icon_html}
                <h3 style="color: {color}; margin-top: 0;">{title}</h3>
            </div>
            {f'<p style="color: #FFFFFF; margin-bottom: 0;">{content}</p>' if content else ''}
        </div>
        """,
        unsafe_allow_html=True
    )

def initialize_session_state():
    """Initialize session state variables"""
    if 'step' not in st.session_state:
        st.session_state.step = 'platform_choice'
    if 'platform' not in st.session_state:
        st.session_state.platform = None
    if 'emergency_type' not in st.session_state:
        st.session_state.emergency_type = None
    if 'current_location' not in st.session_state:
        st.session_state.current_location = None
    if 'text_address' not in st.session_state:
        st.session_state.text_address = None
    if 'location_choice' not in st.session_state:
        st.session_state.location_choice = None
    if 'photos' not in st.session_state:
        st.session_state.photos = []
    if 'alert_sent' not in st.session_state:
        st.session_state.alert_sent = False
    if 'emergency_status' not in st.session_state:
        st.session_state.emergency_status = None
    if 'estimated_time' not in st.session_state:
        st.session_state.estimated_time = None
    if 'dispatch_time' not in st.session_state:
        st.session_state.dispatch_time = None

def get_estimated_time():
    """Return a random estimated arrival time between 5-15 minutes"""
    return randint(5, 15)

def show_progress_bar():
    """Show an animated progress bar"""
    progress_bar = st.progress(0)
    for percent_complete in range(100):
        time.sleep(0.03)  # Slower animation
        progress_bar.progress(percent_complete + 1)
    time.sleep(0.5)
    progress_bar.empty()

def main():
    # Set dark theme
    st.set_page_config(
        page_title="Emergency Assistance",
        page_icon="🚑",
        layout="centered",
        initial_sidebar_state="collapsed",
        menu_items={
            'Get Help': None,
            'Report a bug': None,
            'About': None
        }
    )

    # Initialize session state
    initialize_session_state()

    # Custom CSS for dark theme with white text
    st.markdown("""
        <style>
        /* Dark theme styles */
        body {
            background-color: #121212;
            color: #FFFFFF;
        }
        .main {
            padding: 2rem;
            max-width: 900px;
            margin: 0 auto;
            background-color: #121212;
        }
        .stButton button {
            width: 100%;
            border-radius: 20px;
            height: 3em;
            font-weight: 600;
            background-color: #2C2C2C;
            color: #FFFFFF;
            border: 1px solid #404040;
            transition: all 0.3s ease;
        }
        .stButton button:hover {
            background-color: #404040;
            border-color: #505050;
            transform: scale(1.02);
        }
        .emergency-title {
            color: #FF4B4B;
            text-align: center;
            margin-bottom: 1em;
            font-size: 2.5em;
        }
        .stTextInput input, .stTextArea textarea {
            background-color: #2C2C2C;
            color: #FFFFFF;
            border: 1px solid #404040;
        }
        .stTextInput input:focus, .stTextArea textarea:focus {
            border-color: #505050;
            box-shadow: 0 0 0 1px #505050;
        }
        .uploadedFile {
            background-color: #2C2C2C;
            color: #FFFFFF;
            border: 1px solid #404040;
        }
        .css-1d391kg {
            background-color: #1E1E1E;
        }
        .folium-map {
            border: 2px solid #404040;
            border-radius: 10px;
        }
        /* Override Streamlit's default white background */
        .stApp {
            background-color: #121212;
        }
        /* Emergency type buttons */
        .emergency-btn {
            height: 120px !important;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            font-size: 1.2em !important;
        }
        .emergency-btn span {
            font-size: 2em;
            margin-bottom: 10px;
        }
        /* Progress bar styling */
        .stProgress > div > div > div {
            background-color: #FF4B4B;
        }
        /* All text elements to white */
        p, li, div, span, .stMarkdown, .stAlert, .stSuccess, .stWarning, .stError {
            color: #FFFFFF !important;
        }
        /* Input labels */
        label {
            color: #FFFFFF !important;
        }
        /* Expander headers */
        .stExpander label {
            color: #FFFFFF !important;
        }
        /* Dataframe text */
        .stDataFrame {
            color: #FFFFFF !important;
        }
        </style>
    """, unsafe_allow_html=True)

    if not st.session_state.alert_sent:
        st.markdown('<h1 class="emergency-title">🚑 Emergency Assistance</h1>', unsafe_allow_html=True)

        if st.session_state.step == 'platform_choice':
            custom_card("Choose how you'd like to continue", 
                      "Select your preferred method to request emergency assistance", 
                      color="#1E88E5", icon="📱")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Continue Here", use_container_width=True, 
                           help="Complete the emergency request in this web interface"):
                    st.session_state.platform = "streamlit"
                    st.session_state.step = 'emergency_type'
                    st.rerun()
            with col2:
                if st.button("Open in Telegram", use_container_width=True,
                            help="Continue with our Telegram bot for faster assistance"):
                    bot_username = "CareGenieBot"
                    telegram_url = f"https://t.me/{bot_username}"
                    st.markdown(f"[Open Telegram Bot]({telegram_url})")
                    st.stop()

        elif st.session_state.step == 'emergency_type':
            custom_card("Select Emergency Type", 
                      "Choose the type that best matches your situation", 
                      color="#FF4B4B", icon="⚠️")
            
            emergency_options = {
                "Medical Emergency": {"emoji": "🏥", "color": "#FF4B4B"},
                "Accident": {"emoji": "🚗", "color": "#FF9800"},
                "Heart/Chest Pain": {"emoji": "❤️", "color": "#F44336"},
                "Pregnancy": {"emoji": "👶", "color": "#E91E63"},
                "Fire": {"emoji": "🔥", "color": "#FF5722"},
                "Other Emergency": {"emoji": "🆘", "color": "#9C27B0"}
            }
            
            cols = st.columns(2)
            for i, (option, details) in enumerate(emergency_options.items()):
                with cols[i % 2]:
                    if st.button(
                        f"{details['emoji']} {option}", 
                        use_container_width=True,
                        key=f"emergency_{i}",
                        help=f"Select for {option} situation"
                    ):
                        st.session_state.emergency_type = option
                        st.session_state.step = 'location_choice'
                        st.rerun()

        elif st.session_state.step == 'location_choice':
            custom_card("Share Your Location", 
                      "Help us locate you quickly for faster response", 
                      color="#4CAF50", icon="📍")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📍 Share Location on Map", 
                           use_container_width=True,
                           help="Select your precise location on a map"):
                    st.session_state.location_choice = "location"
                    st.session_state.step = 'current_location'
                    st.rerun()
                
            with col2:
                if st.button("✍️ Enter Address Manually", 
                           use_container_width=True,
                           help="Type your address if you can't share location"):
                    st.session_state.location_choice = "address"
                    st.session_state.step = 'text_address'
                    st.rerun()

        elif st.session_state.step == 'current_location':
            custom_card("Select Your Location on the Map", 
                      "Click on the map to mark your exact location", 
                      color="#4CAF50", icon="🗺️")
            
            # Create a dark-themed map centered on India by default
            map_center = [20.5937, 78.9629]  # Center of India
            m = folium.Map(
                location=map_center,
                zoom_start=5,
                tiles="cartodbdark_matter",  # Dark theme tiles
                control_scale=True
            )
            
            # Add a marker if location is already selected
            if st.session_state.current_location:
                folium.Marker(
                    [st.session_state.current_location['latitude'], 
                     st.session_state.current_location['longitude']],
                    popup="Emergency Location",
                    icon=folium.Icon(color="red", icon="exclamation-triangle")
                ).add_to(m)
            
            map_data = st_folium(m, width=700, height=500)

            if map_data.get("last_clicked"):
                latitude, longitude = map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"]
                st.session_state.current_location = {"latitude": latitude, "longitude": longitude}
                
                # Show confirmation and next steps
                st.success(f"Location captured: {latitude:.6f}, {longitude:.6f}")
                
                # Show a preview of the location
                with st.expander("📍 Location Preview"):
                    try:
                        geolocator = Nominatim(user_agent="emergency_app")
                        location = geolocator.reverse(f"{latitude}, {longitude}")
                        if location and location.address:
                            st.write("**Approximate Address:**")
                            st.write(location.address)
                    except Exception as geo_error:
                        st.warning("Couldn't fetch address details for this location")
                    
                    st.write(f"**Google Maps Link:**")
                    st.write(f"https://www.google.com/maps?q={latitude},{longitude}")

                if st.button("Confirm Location", use_container_width=True):
                    st.session_state.step = 'photos'
                    st.rerun()

        elif st.session_state.step == 'text_address':
            custom_card("Enter Your Address", 
                      "Please provide as much detail as possible", 
                      color="#4CAF50", icon="🏠")
            
            text_address = st.text_area(
                "Complete Address (Include landmarks if possible):",
                placeholder="e.g., 123 Main Street, Apartment 4B, Near Central Park, Mumbai, Maharashtra 400001"
            )
            
            if st.button("Continue", use_container_width=True):
                if text_address.strip():
                    st.session_state.text_address = text_address
                    
                    # Try to geocode the address to confirm it's valid
                    try:
                        geolocator = Nominatim(user_agent="emergency_app")
                        location = geolocator.geocode(text_address)
                        if location:
                            st.session_state.current_location = {
                                "latitude": location.latitude,
                                "longitude": location.longitude
                            }
                            st.success("Address verified and location coordinates captured")
                        else:
                            st.warning("Couldn't find exact coordinates for this address, but we'll still proceed")
                    except Exception as e:
                        st.warning(f"Address verification failed: {str(e)}")
                    
                    st.session_state.step = 'photos'
                    st.rerun()
                else:
                    st.error("Please enter a valid address")

        elif st.session_state.step == 'photos':
            custom_card("Upload Photos (Optional)", 
                      "Visual information helps responders prepare", 
                      color="#9C27B0", icon="📷")
            
            uploaded_files = st.file_uploader(
                "Upload photos of the emergency situation:",
                type=["jpg", "jpeg", "png"],
                accept_multiple_files=True,
                help="Upload clear photos showing the situation, injuries, or surroundings"
            )
            
            # Show preview of uploaded images
            if uploaded_files:
                st.write("**Image Previews:**")
                cols = st.columns(3)
                for i, file in enumerate(uploaded_files):
                    with cols[i % 3]:
                        st.image(file, use_column_width=True)
            
            if st.button("Send Emergency Alert", use_container_width=True):
                if uploaded_files:
                    st.session_state.photos = uploaded_files
                
                st.session_state.step = 'summary'
                st.rerun()

        elif st.session_state.step == 'summary':
            custom_card("Confirm Emergency Details", 
                      "Please review before sending", 
                      color="#FF9800", icon="🔍")
            
            # Display all collected information
            st.write("**Emergency Type:**")
            st.write(st.session_state.emergency_type)
            
            st.write("**Location Information:**")
            if st.session_state.current_location:
                st.write(f"Coordinates: {st.session_state.current_location['latitude']:.6f}, " +
                        f"{st.session_state.current_location['longitude']:.6f}")
                st.write(f"[View on Google Maps](https://www.google.com/maps?q=" +
                        f"{st.session_state.current_location['latitude']}," +
                        f"{st.session_state.current_location['longitude']})")
            
            if st.session_state.text_address:
                st.write(f"Address: {st.session_state.text_address}")
            
            st.write("**Photos Attached:**")
            st.write(f"{len(st.session_state.photos)} image(s)" if st.session_state.photos else "None")
            
            if st.button("🚨 CONFIRM AND SEND ALERT 🚨", 
                        use_container_width=True,
                        type="primary"):
                
                emergency_details = {
                    'type': st.session_state.emergency_type,
                    'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'current_location': st.session_state.current_location,
                    'text_address': st.session_state.text_address
                }

                with st.spinner("Dispatching Emergency Services..."):
                    show_progress_bar()
                    if send_emergency_alert_to_admin(emergency_details, st.session_state.photos):
                        st.session_state.alert_sent = True
                        st.session_state.emergency_status = "en_route"
                        st.session_state.estimated_time = get_estimated_time()
                        st.session_state.dispatch_time = datetime.now()
                        st.rerun()
                    else:
                        st.error("Failed to send alert. Please try again.")

    else:
        # Emergency services dispatched view
        st.markdown('<h1 class="emergency-title">🚑 Emergency Services En Route</h1>', unsafe_allow_html=True)
        
        # Calculate time since dispatch
        time_since_dispatch = (datetime.now() - st.session_state.dispatch_time).seconds // 60
        
        custom_card(
            "🚑 Help is on the way!",
            f"""
            <div style="font-size: 1.2em;">
                <p><strong>Estimated arrival time:</strong> {st.session_state.estimated_time} minutes</p>
                <p><strong>Time since dispatch:</strong> {time_since_dispatch} minutes</p>
                <p><strong>Emergency type:</strong> {st.session_state.emergency_type}</p>
            </div>
            """,
            "#4CAF50",
            "⏱️"
        )

        custom_card(
            "📝 Important Instructions",
            """
            <div style="font-size: 1.1em;">
            <ul style="margin-top: 0; padding-left: 20px;">
                <li>Stay calm and remain in your current location</li>
                <li>Keep your phone nearby and charged</li>
                <li>Gather any relevant medical documents or medications</li>
                <li>Clear the path for emergency responders</li>
                <li>If possible, have someone wait outside to guide the team</li>
                <li>Follow any first aid procedures you know</li>
                <li>Do not move injured persons unless absolutely necessary</li>
            </ul>
            </div>
            """,
            "#1E88E5",
            "📋"
        )

        custom_card(
            "🆘 Emergency Contact",
            """
            <div style="font-size: 1.1em;">
            <p>If your condition worsens or you need immediate assistance:</p>
            <p style="font-weight: bold; font-size: 1.3em; color: #FF4B4B;">Call 112 (India Emergency Number)</p>
            <p>Or contact our emergency line: <strong>+91-XXX-XXX-XXXX</strong></p>
            </div>
            """,
            "#FF4B4B",
            "📞"
        )

        # Show location map if available
        if st.session_state.current_location:
            with st.expander("📍 Your Location", expanded=True):
                m = folium.Map(
                    location=[st.session_state.current_location['latitude'], 
                             st.session_state.current_location['longitude']],
                    zoom_start=15,
                    tiles="cartodbdark_matter"
                )
                folium.Marker(
                    [st.session_state.current_location['latitude'], 
                     st.session_state.current_location['longitude']],
                    popup="Your Location",
                    icon=folium.Icon(color="red", icon="exclamation-triangle")
                ).add_to(m)
                st_folium(m, width=700, height=400)

        # Reset button (bottom of page)
        st.markdown("---")
        if st.button("Start New Emergency Request", 
                    use_container_width=True,
                    type="secondary"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

if __name__ == "__main__":
    main()
