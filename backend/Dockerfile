FROM python:3.12-slim

# системные программы
# Нам нужны git, wget, unzip и компиляторы (gcc, make) для установки инструментов
RUN apt-get update && apt-get install -y \
    git \
    wget \
    unzip \
    build-essential \
    libpcap-dev \
    clang \
    nmap \
    && rm -rf /var/lib/apt/lists/*


# Amass (поиск поддоменов)
WORKDIR /tmp
RUN wget https://github.com/owasp-amass/amass/releases/download/v4.2.0/amass_Linux_amd64.zip \
    && unzip amass_Linux_amd64.zip \
    && mv amass_Linux_amd64/amass /usr/local/bin/ \
    && rm -rf amass_Linux_amd64*

# Masscan (быстрый сканер портов)
WORKDIR /tmp
RUN git clone https://github.com/robertdavidgraham/masscan \
    && cd masscan \
    && make \
    && make install \
    && rm -rf /tmp/masscan

# theHarvester
WORKDIR /opt
RUN git clone https://github.com/laramies/theHarvester.git
WORKDIR /opt/theHarvester
# Устанавливаем сам пакет и его зависимости одной командой
RUN pip install .


WORKDIR /app

COPY requirements.txt /app/

RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

# контейнер будет слушать порт 8000
EXPOSE 8000

# запуск сервера
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
