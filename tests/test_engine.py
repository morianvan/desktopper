import random
import unittest
from pet.engine import Animator, Behavior, Clip, bounded_motion


def clips():
    return {
        "idle": Clip(tuple(range(6)), 4),
        "walk": Clip(tuple(range(6)), 9),
        "stim": Clip(tuple(range(4)), 5),
        "run": Clip(tuple(range(4, 8)), 12),
        "knife": Clip(tuple(range(16)), 10, "idle"),
        "jumppad": Clip(tuple(range(16)), 8, "idle"),
    }


class EngineTests(unittest.TestCase):
    def test_specials_show_last_frame_then_return_to_idle(self):
        for state in ("knife", "jumppad"):
            with self.subTest(state=state):
                player = Animator(clips())
                player.request(state.upper())
                duration = len(clips()[state].frames) / clips()[state].fps
                player.advance(duration - 0.001)
                self.assertEqual((player.state, player.frame_position), (state, 15))
                completed = player.advance(0.002)
                self.assertEqual(completed, (state,))
                self.assertEqual(player.state, "idle")
                player.advance(10)
                self.assertEqual(player.state, "idle")

    def test_auto_timer_cannot_interrupt_special_or_skip_idle(self):
        for state in ("knife", "jumppad"):
            with self.subTest(state=state):
                behavior = Behavior(clips(), {"duration_seconds": [3, 3], "walk_speed": 75, "run_speed": 300})
                behavior.choose(state)
                behavior.remaining = -10
                behavior.advance(0.2)
                self.assertEqual(behavior.animator.state, state)
                self.assertEqual(behavior.speed, 0)
                behavior.advance(2)
                self.assertEqual(behavior.animator.state, "idle")
                self.assertEqual(behavior.remaining, 3)
                behavior.advance(1)
                self.assertEqual(behavior.animator.state, "idle")

    def test_manual_special_returns_without_enabling_auto(self):
        behavior = Behavior(clips(), {"duration_seconds": [3, 3], "walk_speed": 75, "run_speed": 300})
        behavior.auto = False
        behavior.choose("knife")
        behavior.advance(2)
        self.assertEqual(behavior.animator.state, "idle")
        self.assertFalse(behavior.auto)

    def test_random_mode_can_reach_every_action(self):
        behavior = Behavior(clips(), {"duration_seconds": [1, 1], "walk_speed": 75, "run_speed": 300}, random.Random(5))
        visited = set()
        for _ in range(5000):
            behavior.advance(0.05)
            visited.add(behavior.animator.state)
        self.assertEqual(visited, {"idle", "walk", "stim", "run", "knife", "jumppad"})

    def test_stim_once_then_loop_with_remainder(self):
        player = Animator(clips())
        player.request("run")
        self.assertEqual(player.state, "stim")
        player.advance(0.79)
        self.assertEqual(player.frame_position, 3)
        player.advance(0.11)
        self.assertEqual(player.state, "run")
        self.assertEqual(player.frame_position, 1)
        player.advance(20)
        self.assertEqual(player.state, "run")
        self.assertIn(player.frame_position, range(4))

    def test_repeated_run_does_not_reinject_but_new_run_does(self):
        player = Animator(clips())
        player.request("run")
        player.advance(0.4)
        player.request("run")
        self.assertAlmostEqual(player.elapsed, 0.4)
        player.advance(0.5)
        player.request("run")
        self.assertEqual(player.state, "run")
        player.request("idle")
        player.advance(0.25)
        self.assertEqual(player.state, "idle")
        player.request("run")
        self.assertEqual((player.state, player.elapsed), ("stim", 0))

    def test_intro_stationary_and_not_cut_short_by_random_timer(self):
        behavior = Behavior(clips(), {"duration_seconds": [0.1, 0.1], "walk_speed": 75, "run_speed": 300}, random.Random(2))
        behavior.choose("run")
        for _ in range(7):
            behavior.advance(0.1)
            self.assertEqual(behavior.animator.state, "stim")
            self.assertEqual(behavior.speed, 0)
        behavior.advance(0.11)
        self.assertEqual(behavior.animator.state, "run")
        self.assertGreater(behavior.speed, 0)
        self.assertLess(behavior.speed, 300)

    def test_durations_and_loop_start_skip_launch_pose(self):
        data = clips()
        data["run"] = Clip((4, 5, 6), 10, durations_ms=(100, 200, 100), loop_start=1)
        player = Animator(data)
        player.request("run")
        player.advance(0.8)
        self.assertEqual((player.state, player.frame_position), ("run", 0))
        player.advance(0.11)
        self.assertEqual(player.frame_position, 1)
        player.advance(0.3)
        self.assertEqual(player.frame_position, 1)
        for _ in range(100):
            player.advance(0.01)
            self.assertNotEqual(player.frame_position, 0)

    def test_manual_request_waits_for_landing_and_idle_settle(self):
        data = clips()
        data["idle"] = Clip((0, 1), 4, exit_frames=(0, 1))
        player = Animator(data)
        player.request("jumppad")
        player.advance(0.5)
        player.request("knife")
        player.advance(1.49)
        self.assertEqual(player.state, "jumppad")
        self.assertEqual(player.pending, "knife")
        player.advance(0.02)
        self.assertEqual(player.state, "idle")
        player.advance(0.2)
        self.assertEqual(player.state, "idle")
        player.advance(0.05)
        self.assertEqual(player.state, "knife")

    def test_locomotion_stops_before_handling_prop(self):
        data = clips()
        data["idle"] = Clip((0, 1), 4, exit_frames=(0, 1))
        player = Animator(data)
        player.request("walk")
        player.advance(0.1)
        player.request("jumppad")
        player.advance(0.57)
        self.assertEqual(player.state, "idle")
        self.assertEqual(player.pending, "jumppad")
        player.advance(0.25)
        self.assertEqual(player.state, "jumppad")

    def test_newest_queued_action_wins(self):
        player = Animator(clips())
        player.request("jumppad")
        player.request("knife")
        player.request("walk")
        self.assertEqual(player.pending, "walk")
        player.advance(2.3)
        self.assertEqual(player.state, "idle")  # default V1 idle exits at its end
        player.advance(1.3)
        self.assertEqual(player.state, "walk")

    def test_acceleration_is_bounded_and_stationary_actions_do_not_slide(self):
        behavior = Behavior(clips(), {"duration_seconds": [3, 3], "walk_speed": 75, "run_speed": 300})
        behavior.auto = False
        behavior.choose("walk")
        behavior.advance(0.01)
        self.assertAlmostEqual(behavior.speed, 9)
        behavior.advance(0.1)
        self.assertEqual(behavior.speed, 75)
        behavior.choose("knife")
        behavior.advance(0.6)
        self.assertEqual(behavior.animator.state, "idle")
        self.assertEqual(behavior.speed, 0)

    def test_large_time_step_matches_small_steps(self):
        data = clips()
        data["run"] = Clip((4, 5, 6), 10, durations_ms=(100, 80, 120), loop_start=1)
        a, b = Animator(data), Animator(data)
        a.request("run")
        b.request("run")
        a.advance(4.321)
        for _ in range(4321):
            b.advance(0.001)
        self.assertEqual((a.state, a.frame_position), (b.state, b.frame_position))
        self.assertAlmostEqual(a.elapsed, b.elapsed, places=6)

    def test_edges_and_negative_monitor_coordinates(self):
        result = bounded_motion(-245, 5, 1, -0.2, 300, 0.1, (-1920, 0, -240, 840))
        self.assertEqual(result, (-240, 0, -1, 0.2))
        result = bounded_motion(-1919, 839, -1, 1, 300, 0.1, (-1920, 0, -240, 840))
        self.assertEqual(result, (-1920, 840, 1, -1))

    def test_oversized_window_is_clamped_without_inverted_range(self):
        self.assertEqual(bounded_motion(40, 40, 1, 1, 0, 0, (0, 0, -10, -10))[:2], (0, 0))


if __name__ == "__main__":
    unittest.main()
