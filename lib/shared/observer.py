class Disposer():
    def __init__(self, observer, observable):
        self._observer = observer;
        self._observable = observable;

    def __del__(self):
        self._observable.Unsubscribe(self._observer);

class Observable:
    def __init__(self):
        self._observers = list();

    def Subscribe(self, observer) -> Disposer:
        if not observer in self._observers:
            self._observers.append(observer);
            disposer = Disposer(observer, self);
            return disposer;
        return None;

    def Unsubscribe(self, observer):
        if observer in self._observers:
            self._observers.remove(observer);
    
    # NOT THREAD SAFE, MIND THAT IN OBSERVER CALLBACK IMPLS
    def Raise(self, event : any):
        for observer in self._observers:
            observer.OnEvent(event);

class Observer():
    def __init__(self, callback):
        self._disposer = None;
        self._callback = callback;
    
    def __del__(self):
        del self._disposer;
        self._disposer = None;
    
    def Subscribe(self, observable : Observable):
        self._disposer = observable.Subscribe(self);

    # NOT THREAD SAFE WHEN CALLED FROM OBSERVABLE ( PROVIDER CAN RUN ON SEPARATE THREAD ) 
    def OnEvent(self, event):
        self._callback(event);