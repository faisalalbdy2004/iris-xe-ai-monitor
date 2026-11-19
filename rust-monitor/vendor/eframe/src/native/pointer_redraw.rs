//! Paint comparison for CorePulse's optional native Wayland scheduling policy.
use super::egui;
use egui::epaint::Primitive;
use egui::{ClippedPrimitive, Event};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) enum FrameInput {
    Idle,
    Motion,
    Other,
}

impl FrameInput {
    pub(super) fn from_events(events: &[Event], interaction_active: bool) -> Self {
        if interaction_active {
            Self::Other
        } else if events.is_empty() {
            Self::Idle
        } else if events
            .iter()
            .all(|event| matches!(event, Event::PointerMoved(_)))
        {
            Self::Motion
        } else {
            Self::Other
        }
    }
}

pub(super) struct PaintFrame {
    geometry: ([u32; 2], f32, [f32; 4]),
    pub(super) primitives: Vec<ClippedPrimitive>,
}

impl PaintFrame {
    pub(super) fn new(
        framebuffer_size: [u32; 2],
        scale: f32,
        clear_color: [f32; 4],
        primitives: Vec<ClippedPrimitive>,
    ) -> Self {
        Self {
            geometry: (framebuffer_size, scale, clear_color),
            primitives,
        }
    }

    fn matches(&self, previous: &Self) -> bool {
        self.geometry == previous.geometry
            && self.primitives.len() == previous.primitives.len()
            && self
                .primitives
                .iter()
                .zip(&previous.primitives)
                .all(|(a, b)| {
                    a.clip_rect == b.clip_rect
                        && matches!((&a.primitive, &b.primitive),
                        (Primitive::Mesh(a), Primitive::Mesh(b)) if a == b)
                })
    }
}

#[derive(Default)]
pub(super) struct PointerRedraws {
    previous: Option<PaintFrame>,
    remaining_followups: u8,
}

impl PointerRedraws {
    pub(super) fn invalidate(&mut self) {
        *self = Self::default();
    }

    pub(super) fn should_skip(
        &mut self,
        frame: PaintFrame,
        input: FrameInput,
        paint_only: bool,
    ) -> bool {
        let skip = paint_only
            && input == FrameInput::Idle
            && self.remaining_followups > 0
            && self
                .previous
                .as_ref()
                .is_some_and(|previous| frame.matches(previous));
        self.previous = Some(frame);
        self.remaining_followups = match input {
            FrameInput::Motion if paint_only => 2,
            FrameInput::Idle if skip => self.remaining_followups - 1,
            _ => 0,
        };
        skip
    }

    pub(super) fn primitives(&self) -> &[ClippedPrimitive] {
        self.previous
            .as_ref()
            .map_or(&[], |frame| frame.primitives.as_slice())
    }
}
