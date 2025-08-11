kubectl cp ./syncer.py arha-system/controller-deployment-54485ffb6b-d2m6c:/app/syncer.py -c crd-syncer

kubectl get services.ha.example.com -n arha-system

kubectl get services.ha.example.com service-info -n arha-system -o yaml
