##  Project Setup

cd whatsx
2. Create & Activate Virtual Environment
Windows


python -m venv venv
venv\Scripts\activate

Mac / Linux
python3 -m venv venv
source venv/bin/activate

3. Install Python Dependencies
pip install -r requirements.txt

4. Apply Database Migrations
python manage.py makemigrations
python manage.py migrate


5. Create Superuser (Admin Account)
python manage.py createsuperuser

6. Run the Django Server

python manage.py runserver
Now visit:
 http://127.0.0.1:8000

 WhatsApp Service Setup (Node.js) in new terminal
1. Move into whatsapp-service Folder
cd whatsapp-service
2. Install Node Dependencies
npm install
3. Start the WhatsApp Session Service
node index.js

Celery + Redis (Message Sending) in new terminal
sudo apt install redis-server
redis-server
celery -A core  worker -l info --pool=prefork
celery -A core beat -l info
