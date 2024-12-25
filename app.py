from flask import Flask, render_template_string, request, redirect, session, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import DecimalField, SubmitField
from wtforms.validators import DataRequired
import requests
from datetime import datetime
import pandas as pd
import plotly.express as px
import plotly.io as pio

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
db = SQLAlchemy(app)

# API Keys
openweathermapApiKey = '6e6d0e2dfd9d624831e5ed1f669981e3'
aqiApiKey = '132f67be1b7c0decb2f2135bafb77d0f692bec9a'
newsApiKey = 'pub_606810caeef4343f08808351b7ea3c950f664'

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))

    def __init__(self, username, password):
        self.username = username
        self.password = password

class CarbonLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    transport = db.Column(db.Float, nullable=False)
    electricity = db.Column(db.Float, nullable=False)
    waste = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow)
class CarbonLogForm(FlaskForm):
    transport = DecimalField('Transport (kg CO2)', validators=[DataRequired()])
    electricity = DecimalField('Electricity (kg CO2)', validators=[DataRequired()])
    waste = DecimalField('Waste (kg CO2)', validators=[DataRequired()])
    submit = SubmitField('Log Carbon Data')

@app.route('/register/', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            username = request.form['username']
            password = request.form['password']
            db.session.add(User(username=username, password=password))
            db.session.commit()
            return redirect(url_for('login'))
        except Exception as e:
            return render_template_string(register_html, message="Registration failed.")
    return render_template_string(register_html)

@app.route('/login/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']
        data = User.query.filter_by(username=u, password=p).first()
        if data is not None:
            session['logged_in'] = True
            session['user_id'] = data.id
            return redirect(url_for('dashboard'))
        return render_template_string(login_html, message="Login failed.")
    return render_template_string(login_html)

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.pop('logged_in', None)
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/')
def index():
    return render_template_string(index_html)
@app.route('/dashboard/', methods=['GET', 'POST'])
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    city = request.args.get('city', '')
    weather = None
    aqi = None
    news = []  # Initialize news as an empty list
    error_message = None

    if request.method == 'POST':
        city = request.form.get('city')
        if not city:
            error_message = "Please enter a city name."
        else:
            # Fetch Weather Data
            weather_url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={openweathermapApiKey}&units=metric"
            try:
                response = requests.get(weather_url).json()
                if response["cod"] == 200:
                    weather = {
                        "temperature": response["main"]["temp"],
                        "humidity": response["main"]["humidity"],
                        "wind_speed": response["wind"]["speed"],
                        "visibility": response["visibility"] / 1000,  # Convert meters to kilometers
                        "pressure": response["main"]["pressure"]
                    }
                    lat, lon = response["coord"]["lat"], response["coord"]["lon"]

                    # Fetch AQI Data
                    aqi_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={openweathermapApiKey}"
                    aqi_response = requests.get(aqi_url).json()
                    if "list" in aqi_response and len(aqi_response["list"]) > 0:
                        aqi_value = aqi_response["list"][0]["main"]["aqi"]
                        descriptions = ["Good", "Fair", "Moderate", "Poor", "Very Poor"]
                        aqi = {"aqi": aqi_value, "description": descriptions[aqi_value - 1]}

                    # Fetch News Data
                    news_url = f"https://newsdata.io/api/1/news?apikey={newsApiKey}&q=climate"
                    news_response = requests.get(news_url).json()
                    if "results" in news_response:
                        news = news_response["results"][:5]  # Top 5 headlines

                else:
                    error_message = "City not found. Please try another city."
            except Exception as e:
                error_message = f"An error occurred: {e}"

    return render_template_string(dashboard_html, city=city, weather=weather, aqi=aqi, news=news, error_message=error_message)

@app.route('/carbon_tracker/', methods=['GET', 'POST'])
def carbon_tracker():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    form = CarbonLogForm()
    user_id = session.get('user_id')

    if form.validate_on_submit():
        new_log = CarbonLog(
            user_id=user_id,
            transport=form.transport.data,
            electricity=form.electricity.data,
            waste=form.waste.data
        )
        db.session.add(new_log)
        db.session.commit()
        return redirect(url_for('carbon_tracker'))

    logs = CarbonLog.query.filter_by(user_id=user_id).all()
    df = pd.DataFrame([
        {'date': log.date, 'carbon_footprint': log.transport + log.electricity + log.waste}
        for log in logs
    ])

    chart_html = ""
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
        df = df.groupby('date').sum().reset_index()
        fig = px.line(df, x='date', y='carbon_footprint', title='Carbon Footprint Over Time', labels={'carbon_footprint': 'Carbon Footprint (kg CO2)', 'date': 'Date'})
        chart_html = pio.to_html(fig, full_html=False)

    return render_template_string(carbon_tracker_html, form=form, chart=chart_html)

# HTML Templates
index_html = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #f4f4f4; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        h1 { font-size: 30px; text-align: center; }
    </style>
</head>
<body>
    <h1>Welcome to the Weather Dashboard!</h1>
    <a href="/login">Login</a> | <a href="/register">Register</a>
</body>
</html>
'''

login_html = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #f4f4f4; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .login-container { background-color: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1); width: 300px; }
        h2 { text-align: center; margin-bottom: 20px; }
        input[type="text"], input[type="password"] { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ccc; border-radius: 4px; }
        input[type="submit"] { width: 100%; padding: 10px; background-color: #007bff; color: #fff; border: none; border-radius: 4px; cursor: pointer; }
        input[type="submit"]:hover { background-color: #0056b3; }
        .error-message { color: red; text-align: center; font-size: 14px; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="login-container">
        <h2>Login</h2>
        <form method="POST" action="/login">
            <label for="username">Username</label>
            <input type="text" id="username" name="username" required>
            <label for="password">Password</label>
            <input type="password" id="password" name="password" required>
            <input type="submit" value="Login">
        </form>
        {% if message %}
        <div class="error-message">
            <p>{{ message }}</p>
        </div>
        {% endif %}
    </div>
</body>
</html>
'''

register_html = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Register</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #f4f4f4; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .register-container { background-color: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1); width: 300px; }
        h2 { text-align: center; margin-bottom: 20px; }
        input[type="text"], input[type="password"] { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ccc; border-radius: 4px; }
        input[type="submit"] { width: 100%; padding: 10px; background-color: #007bff; color: #fff; border: none; border-radius: 4px; cursor: pointer; }
        input[type="submit"]:hover { background-color: #0056b3; }
        .error-message { color: red; text-align: center; font-size: 14px; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="register-container">
        <h2>Register</h2>
        <form method="POST" action="/register">
            <label for="username">Username</label>
            <input type="text" id="username" name="username" required>
            <label for="password">Password</label>
            <input type="password" id="password" name="password" required>
            <input type="submit" value="Register">
        </form>
        {% if message %}
        <div class="error-message">
            <p>{{ message }}</p>
        </div>
        {% endif %}
    </div>
</body>
</html>
'''

dashboard_html = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Weather, AQI, and News Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
    <style>
        body {
            background-color: #f8f9fa;
            font-family: Arial, sans-serif;
        }
        .container {
            margin-top: 50px;
            max-width: 800px;
        }
        .card {
            margin-top: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
        }
        .error-message {
            color: red;
            font-weight: bold;
            margin-top: 20px;
        }
        .news-list-item {
            border-bottom: 1px solid #eaeaea;
            padding: 10px 0;
        }
        .news-list-item:last-child {
            border-bottom: none;
        }
        .news-image {
            width: 100%;
            height: auto;
            border-radius: 5px;
            margin-bottom: 10px;
        }
    </style>
    <a href="/carbon_tracker/" class="button">Go to Carbon Tracker</a>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: #f4f4f4; }
        .container { max-width: 800px; margin: 0 auto; padding: 20px; background-color: #fff; border-radius: 8px; box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1); }
        h1 { text-align: center; margin-bottom: 20px; }
        .weather-info, .news { margin-bottom: 20px; }
        .weather-info h3, .news h3 { font-size: 24px; }
        .weather-info p { margin: 5px 0; }
        .news a { text-decoration: none; color: #007bff; display: block; margin: 10px 0; }
        .news a:hover { text-decoration: underline; }
        .news img { max-width: 100%; border-radius: 8px; }
    </style>
</head>
<body>
    <div class="container">
        <h1 class="text-center">Weather, AQI, and News Dashboard</h1>
        <form method="POST" class="mt-4">
            <div class="form-group">
                <label for="city">Enter City</label>
                <input type="text" id="city" name="city" class="form-control" placeholder="Enter city name" value="{{ city }}">
            </div>
            <button type="submit" class="btn btn-primary btn-block">Get Data</button>
        </form>

        {% if error_message %}
        <div class="error-message text-center">
            {{ error_message }}
        </div>
        {% endif %}

        {% if weather %}
        <div class="card">
            <div class="card-body">
                <h5 class="card-title">Weather in {{ city }}</h5>
                <canvas id="weatherChart"></canvas>
                <script>
                    const weatherData = {
                        labels: ['Temperature (°C)', 'Humidity (%)', 'Wind Speed (m/s)', 'Visibility (km)', 'Pressure (hPa)'],
                        datasets: [{
                            label: 'Weather Details',
                            data: [{{ weather.temperature }}, {{ weather.humidity }}, {{ weather.wind_speed }}, {{ weather.visibility }}, {{ weather.pressure }}],
                            backgroundColor: [
                                'rgba(255, 99, 132, 0.2)',
                                'rgba(54, 162, 235, 0.2)',
                                'rgba(255, 206, 86, 0.2)',
                                'rgba(75, 192, 192, 0.2)',
                                'rgba(153, 102, 255, 0.2)'
                            ],
                            borderColor: [
                                'rgba(255, 99, 132, 1)',
                                'rgba(54, 162, 235, 1)',
                                'rgba(255, 206, 86, 1)',
                                'rgba(75, 192, 192, 1)',
                                'rgba(153, 102, 255, 1)'
                            ],
                            borderWidth: 1
                        }]
                    };
                    const weatherConfig = {
                        type: 'bar',
                        data: weatherData,
                        options: {
                            scales: {
                                y: {
                                    beginAtZero: true
                                }
                            }
                        }
                    };
                    new Chart(
                        document.getElementById('weatherChart'),
                        weatherConfig
                    );
                </script>
            </div>
        </div>
        {% endif %}

        {% if aqi %}
        <div class="card">
            <div class="card-body">
                <h5 class="card-title">Air Quality Index (AQI)</h5>
                <p><strong>AQI Value:</strong> {{ aqi.aqi }}</p>
                <p><strong>Description:</strong> {{ aqi.description }}</p>
            </div>
        </div>
        {% endif %}

        {% if news %}
        <div class="card">
            <div class="card-body">
                <h5 class="card-title">Latest News on Climate</h5>
                <ul class="list-unstyled">
                    {% for article in news %}
                    <li class="news-list-item">
                        {% if article.image_url %}
                        <img src="{{ article.image_url }}" alt="News Image" class="news-image">
                        {% endif %}
                        <a href="{{ article.link }}" target="_blank">{{ article.title }}</a>
                        <p class="text-muted">Source: {{ article.source_id }}</p>
                    </li>
                    {% endfor %}
                </ul>
            </div>
        </div>
        {% endif %}
    </div>
</body>
</html>




'''

carbon_tracker_html = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Carbon Tracker</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f4f4f9;
            color: #333;
            margin: 0;
            padding: 0;
        }

        h1 {
            background-color: #4CAF50;
            color: white;
            text-align: center;
            padding: 20px;
            margin: 0;
        }

        h2 {
            text-align: center;
            color: #4CAF50;
        }

        form {
            max-width: 600px;
            margin: 20px auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        }

        label {
            font-weight: bold;
            display: block;
            margin-bottom: 5px;
            color: #4CAF50;
        }

        input[type="number"] {
            width: 100%;
            padding: 10px;
            margin: 10px 0 20px 0;
            border: 1px solid #ccc;
            border-radius: 4px;
            box-sizing: border-box;
        }

        input[type="submit"] {
            background-color: #4CAF50;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            width: 100%;
        }

        input[type="submit"]:hover {
            background-color: #45a049;
        }

        .chart-container {
            margin: 30px auto;
            width: 80%;
            max-width: 1000px;
            text-align: center;
        }

        .container {
            padding: 0 20px;
        }

        .footer {
            background-color: #333;
            color: white;
            text-align: center;
            padding: 15px;
            position: fixed;
            width: 100%;
            bottom: 0;
        }
    </style>
</head>
<body>
    <h1>Carbon Tracker</h1>
    <div class="container">
        <form method="POST">
            {{ form.hidden_tag() }}
            <label for="transport">Transport:</label>
            {{ form.transport }}<br>
            <label for="electricity">Electricity:</label>
            {{ form.electricity }}<br>
            <label for="waste">Waste:</label>
            {{ form.waste }}<br>
            {{ form.submit }}
        </form>
    </div>

    <div class="chart-container">
        <h2>Carbon Footprint Over Time</h2>
        <div>{{ chart|safe }}</div>
    </div>

    <div class="footer">
        <p>S.JYOSHNA A FRIEND FOR THE PRECIOUS FRIEND</p>
    </div>
</body>
</html>

'''



if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
