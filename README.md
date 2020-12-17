# Connect

[![Build Status](https://travis-ci.com/Ilhasoft/connect-engine.svg?branch=main)](https://travis-ci.com/Ilhasoft/connect-engine)
[![Coverage Status](https://coveralls.io/repos/github/Ilhasoft/connect-engine/badge.svg?branch=main)](https://coveralls.io/github/Ilhasoft/connect-engine?branch=main)
[![Python Version](https://img.shields.io/badge/python-3.6-blue.svg)](https://www.python.org/)
[![License GPL-3.0](https://img.shields.io/badge/license-%20GPL--3.0-yellow.svg)](https://github.com/Ilhasoft/connect-engine/blob/master/LICENSE)

## Environment Variables

You can set environment variables in your OS, write on ```.env``` file or pass via Docker config.

| Variable | Type | Default | Description |
|--|--|--|--|
| SECRET_KEY | ```string```|  ```None``` | A secret key for a particular Django installation. This is used to provide cryptographic signing, and should be set to a unique, unpredictable value.
| DEBUG | ```boolean``` | ```False``` | A boolean that turns on/off debug mode.
| ALLOWED_HOSTS | ```string``` | ```*``` | A list of strings representing the host/domain names that this Django site can serve.
| DEFAULT_DATABASE | ```string``` | ```sqlite:///db.sqlite3``` | Read [django-environ](https://django-environ.readthedocs.io/en/latest/) to configure the database connection.
| LANGUAGE_CODE | ```string``` | ```en-us``` | A string representing the language code for this installation.This should be in standard [language ID format](https://docs.djangoproject.com/en/2.0/topics/i18n/#term-language-code).
| TIME_ZONE | ```string``` | ```UTC``` | A string representing the time zone for this installation. See the [list of time zones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).
| STATIC_URL | ```string``` | ```/static/``` | URL to use when referring to static files located in ```STATIC_ROOT```.


## License

Distributed under the GPL-3.0 License. See `LICENSE` for more information.


## Contributing

Contributions are what make the open source community such an amazing place to be learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request
