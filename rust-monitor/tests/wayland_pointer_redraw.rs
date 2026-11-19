//! Use the actual eframe policy without opening a compositor-dependent test window.
use eframe::egui;
use egui::{pos2, Context, Event, RawInput, RequestRepaintInfo, ViewportId};
use std::sync::{Arc, Mutex};
use std::time::Duration;

#[path = "../vendor/eframe/src/native/pointer_redraw.rs"]
mod pointer_redraw;

use pointer_redraw::{FrameInput, PaintFrame, PointerRedraws};

fn paint(size: [u32; 2], color: egui::Color32) -> PaintFrame {
    let mut mesh = egui::Mesh::default();
    let rect = egui::Rect::from_min_max(pos2(0.0, 0.0), pos2(50.0, 50.0));
    mesh.add_colored_rect(rect, color);
    PaintFrame::new(
        size,
        1.0,
        [0.0; 4],
        vec![egui::ClippedPrimitive {
            clip_rect: rect,
            primitive: egui::epaint::Primitive::Mesh(mesh),
        }],
    )
}

#[test]
fn renders_first_motion_and_each_changed_frame() {
    let mut redraws = PointerRedraws::default();
    let size = [820, 610];
    assert!(!redraws.should_skip(paint(size, egui::Color32::RED), FrameInput::Motion, true));
    assert!(redraws.should_skip(paint(size, egui::Color32::RED), FrameInput::Idle, true));
    assert_eq!(redraws.primitives().len(), 1);
    assert!(!redraws.should_skip(paint(size, egui::Color32::BLUE), FrameInput::Idle, true));
    assert!(!redraws.should_skip(paint(size, egui::Color32::BLUE), FrameInput::Idle, true));
}

#[test]
fn resize_and_visibility_changes_keep_the_first_present() {
    let mut redraws = PointerRedraws::default();
    let small = [820, 610];
    let large = [1920, 1006];
    let color = egui::Color32::RED;
    assert!(!redraws.should_skip(paint(small, color), FrameInput::Motion, true));
    assert!(!redraws.should_skip(paint(large, color), FrameInput::Idle, true));
    assert!(!redraws.should_skip(paint(large, color), FrameInput::Motion, true));
    redraws.invalidate(); // Native minimize/restore, focus or exposure.
    assert!(!redraws.should_skip(paint(large, color), FrameInput::Idle, true));
}

#[test]
fn keyboard_click_drag_and_non_paint_work_are_preserved() {
    let movement = [Event::PointerMoved(pos2(10.0, 10.0))];
    assert_eq!(
        FrameInput::from_events(&movement, false),
        FrameInput::Motion
    );
    assert_eq!(FrameInput::from_events(&movement, true), FrameInput::Other);
    let click = [Event::PointerButton {
        pos: pos2(10.0, 10.0),
        button: egui::PointerButton::Primary,
        pressed: true,
        modifiers: egui::Modifiers::NONE,
    }];
    let key = [Event::Key {
        key: egui::Key::Space,
        physical_key: None,
        pressed: true,
        repeat: false,
        modifiers: egui::Modifiers::NONE,
    }];
    for events in [&click[..], &key[..]] {
        assert_eq!(FrameInput::from_events(events, false), FrameInput::Other);
    }
    let mut redraws = PointerRedraws::default();
    let size = [820, 610];
    let color = egui::Color32::RED;
    assert!(!redraws.should_skip(paint(size, color), FrameInput::Motion, true));
    assert!(!redraws.should_skip(paint(size, color), FrameInput::Idle, false));
    assert!(!redraws.should_skip(paint(size, color), FrameInput::Idle, true));
}

#[test]
fn skips_at_most_two_unchanged_followups() {
    let mut redraws = PointerRedraws::default();
    let size = [820, 610];
    let color = egui::Color32::RED;
    assert!(!redraws.should_skip(paint(size, color), FrameInput::Motion, true));
    for _ in 0..2 {
        assert!(redraws.should_skip(paint(size, color), FrameInput::Idle, true));
    }
    assert!(!redraws.should_skip(paint(size, color), FrameInput::Idle, true));
}

#[test]
fn renderer_option_is_off_by_default() {
    assert!(!eframe::NativeOptions::default().experimental_wayland_redraw);
}

fn pointer_carry_after(
    after_motion: impl FnOnce(&Context),
    pointer_only: bool,
) -> (Context, Arc<Mutex<Vec<RequestRepaintInfo>>>, u64) {
    let context = Context::default();
    let callbacks = Arc::new(Mutex::new(Vec::new()));
    let captured = callbacks.clone();
    context.set_request_repaint_callback(move |request| captured.lock().unwrap().push(request));
    for _ in 0..3 {
        let _ = context.run(RawInput::default(), |_| {});
    }
    let motion = RawInput {
        events: vec![Event::PointerMoved(pos2(40.0, 40.0))],
        ..Default::default()
    };
    let _ = context.run(motion, |_| {});
    let pass = context.cumulative_pass_nr_for(ViewportId::ROOT);
    after_motion(&context);
    callbacks.lock().unwrap().clear();
    let _ = context.run(RawInput::default(), |_| {});
    assert!(callbacks.lock().unwrap().iter().any(|request| {
        request.pointer_followup == pointer_only && request.current_cumulative_pass_nr == pass
    }));
    (context, callbacks, pass)
}

fn pointer_carry() -> (Context, Arc<Mutex<Vec<RequestRepaintInfo>>>, u64) {
    pointer_carry_after(|_| {}, true)
}

#[test]
fn a_delayed_request_coalesced_before_the_followup_keeps_its_callback() {
    let _ = pointer_carry_after(
        |ctx| ctx.request_repaint_after(Duration::from_millis(120)),
        false,
    );
}

#[test]
fn retiring_a_carry_rearms_the_next_sensor_wake() {
    let (context, callbacks, pass) = pointer_carry();
    assert!(!context.retire_pointer_followup(ViewportId::ROOT, pass));
    context.mark_unchanged_pointer_pass(ViewportId::ROOT, pass);
    assert!(context.retire_pointer_followup(ViewportId::ROOT, pass));
    callbacks.lock().unwrap().clear();
    // Same operation the worker calls after publishing a fresh sample.
    context.request_repaint();
    let captured = callbacks.lock().unwrap();
    assert_eq!(captured.len(), 1);
    assert!(!captured[0].pointer_followup);
}

#[test]
fn independent_sensor_and_delayed_widget_wakes_block_retirement() {
    for delay in [Duration::ZERO, Duration::from_millis(120)] {
        let (context, _, pass) = pointer_carry();
        context.mark_unchanged_pointer_pass(ViewportId::ROOT, pass);
        context.request_repaint_after(delay);
        assert!(!context.retire_pointer_followup(ViewportId::ROOT, pass));
    }
}

#[test]
fn stale_pass_and_other_viewport_tokens_cannot_retire_current_work() {
    let (context, _, pass) = pointer_carry();
    context.mark_unchanged_pointer_pass(ViewportId::ROOT, pass);
    assert!(!context.retire_pointer_followup(ViewportId::from_hash_of("other"), pass));
    let _ = context.run(RawInput::default(), |_| {});
    assert!(!context.retire_pointer_followup(ViewportId::ROOT, pass));
}
