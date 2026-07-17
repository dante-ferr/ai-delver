use serde_json::Value;
use std::{
    collections::HashMap,
    sync::{
        atomic::AtomicBool,
        Arc, Mutex,
    },
};
use tokio::sync::mpsc;
use uuid::Uuid;

pub enum ReplayMessage {
    Event(Value),
    End,
}

pub struct TrainingSession {
    pub session_id: String,
    pub interrupted: Arc<AtomicBool>,
    pub event_tx: mpsc::UnboundedSender<ReplayMessage>,
    event_rx: Mutex<Option<mpsc::UnboundedReceiver<ReplayMessage>>>,
}

impl TrainingSession {
    pub fn new() -> Self {
        let (event_tx, event_rx) = mpsc::unbounded_channel();
        Self {
            session_id: Uuid::new_v4().to_string(),
            interrupted: Arc::new(AtomicBool::new(false)),
            event_tx,
            event_rx: Mutex::new(Some(event_rx)),
        }
    }

    pub fn take_receiver(&self) -> Option<mpsc::UnboundedReceiver<ReplayMessage>> {
        self.event_rx.lock().ok()?.take()
    }
}

#[derive(Clone, Default)]
pub struct SessionManager {
    inner: Arc<Mutex<HashMap<String, Arc<TrainingSession>>>>,
}

impl SessionManager {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn create(&self) -> Arc<TrainingSession> {
        let session = Arc::new(TrainingSession::new());
        self.inner
            .lock()
            .expect("session map")
            .insert(session.session_id.clone(), Arc::clone(&session));
        session
    }

    pub fn get(&self, session_id: &str) -> Option<Arc<TrainingSession>> {
        self.inner
            .lock()
            .expect("session map")
            .get(session_id)
            .cloned()
    }

    pub fn remove(&self, session_id: &str) {
        if let Ok(mut map) = self.inner.lock() {
            if let Some(session) = map.remove(session_id) {
                let _ = session.event_tx.send(ReplayMessage::End);
            }
        }
    }
}
