### Recipes social site (testing task)

---

#### Compound
***[TODO]***

---

To start application, get into project directory and run:
    
    virtualenv venv
    source venv/bin/activate
    python run.py &

You need the following packages to be installed:
    
`python:v3.7.3`, `virtualenv:v15.1.0`, `mongod:v4.4.5` (MongoDB-CE 4.4)

To prevent creation admin user account with name and password admin:admin,
preset environment variables `RS_ADMIN_NAME` and `RS_ADMIN_PASSWORD`.
Or, to not create at all, set `RS_NO_ADMIN`.

One instance of app perhaps running on my server now:
http://ovz6.n-solenii2016.n03kn.vps.myjino.ru:49319/