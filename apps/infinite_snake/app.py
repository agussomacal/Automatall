import math
import random
import sys
import pygame

# Initialize Pygame
pygame.init()

# Constants
WIDTH, HEIGHT = 800, 600
FPS = 60

# Colors
BLACK = (10, 10, 15)
WHITE = (240, 240, 240)
RED = (231, 76, 60)
BLUE = (52, 152, 219)
GREEN = (46, 204, 113)
GRAY = (120, 120, 120)
YELLOW = (241, 196, 15)


class LightBike:

    def __init__(self, x, y, angle, color, controls, speed, is_ai=False, ai_difficulty="Normal"):
        self.x = float(x)
        self.y = float(y)
        self.angle = angle  # in degrees
        self.speed = speed
        self.turn_speed = 3.5
        self.color = color
        self.controls = controls
        self.trail = []
        self.alive = True
        self.radius = 3
        self.frame_count = 0

        # AI Properties
        self.is_ai = is_ai
        self.ai_difficulty = ai_difficulty
        self.ai_timer = 0
        self.ai_target_turn = 0  # -1 for left, 1 for right, 0 for straight

        # Configure difficulty parameters
        if self.is_ai:
            if ai_difficulty == "Easy":
                self.vision_range = 45
                self.reaction_delay = 12
                self.error_chance = 0.18
            elif ai_difficulty == "Normal":
                self.vision_range = 75
                self.reaction_delay = 6
                self.error_chance = 0.05
            else:  # Hard
                self.vision_range = 110
                self.reaction_delay = 1
                self.error_chance = 0.0

    def update(self, keys_pressed, other_bike, width, height, boundary_mode):
        if not self.alive:
            return

        # Handle turning inputs
        if self.is_ai:
            self.update_ai(other_bike, width, height, boundary_mode)
            if self.ai_target_turn < 0:
                self.angle -= self.turn_speed
            elif self.ai_target_turn > 0:
                self.angle += self.turn_speed
        else:
            if keys_pressed[self.controls['left']]:
                self.angle -= self.turn_speed
            if keys_pressed[self.controls['right']]:
                self.angle += self.turn_speed

        # Intermittent gap logic: every 180 frames (~3 sec), stop leaving a trail for 35 frames
        self.frame_count += 1
        cycle = self.frame_count % 180
        is_leaving_trail = cycle < 145

        if is_leaving_trail:
            self.trail.append((int(self.x), int(self.y)))

        rad = math.radians(self.angle)
        self.x += self.speed * math.cos(rad)
        self.y += self.speed * math.sin(rad)

    def check_ray(self, angle_offset, width, height, other_bike, boundary_mode):
        """Casts a ray to detect obstacles within vision range"""
        rad = math.radians(self.angle + angle_offset)
        step = 6
        for d in range(step, int(self.vision_range), step):
            cx = self.x + d * math.cos(rad)
            cy = self.y + d * math.sin(rad)

            # Check walls
            if boundary_mode == 'Walls':
                if cx < 0 or cx > width or cy < 0 or cy > height:
                    return True

            # Check other bike's trail
            for pt in other_bike.trail:
                if math.hypot(cx - pt[0], cy - pt[1]) <= self.radius + 2:
                    return True

            # Check own trail (excluding recent points)
            if len(self.trail) > 15:
                for pt in self.trail[:-15]:
                    if math.hypot(cx - pt[0], cy - pt[1]) <= self.radius + 2:
                        return True

            # Check head-on collision with other bike
            if math.hypot(cx - other_bike.x, cy - other_bike.y) <= self.radius * 4:
                return True

        return False

    def update_ai(self, other_bike, width, height, boundary_mode):
        self.ai_timer += 1
        if self.ai_timer < self.reaction_delay:
            return
        self.ai_timer = 0

        # Introduce human-like imperfection/error on lower difficulties
        if random.random() < self.error_chance:
            self.ai_target_turn = random.choice([-1, 0, 1])
            return

        # Cast 3 sensor rays
        fwd_danger = self.check_ray(0, width, height, other_bike, boundary_mode)
        left_danger = self.check_ray(-45, width, height, other_bike, boundary_mode)
        right_danger = self.check_ray(45, width, height, other_bike, boundary_mode)

        # Decision logic
        if not fwd_danger:
            self.ai_target_turn = 0  # Prefer going straight if clear
        else:
            if left_danger and not right_danger:
                self.ai_target_turn = 1  # Turn right
            elif right_danger and not left_danger:
                self.ai_target_turn = -1  # Turn left
            else:
                # Both sides blocked or both open, pick randomly
                self.ai_target_turn = random.choice([-1, 1])

    def handle_boundaries(self, width, height, boundary_mode):
        if boundary_mode == 'Walls':
            pass
        else:  # Periodic / Wrap-around
            if self.x < 0:
                self.x = width
            elif self.x > width:
                self.x = 0
            if self.y < 0:
                self.y = height
            elif self.y > height:
                self.y = 0

    def draw(self, surface):
        if len(self.trail) > 1:
            for i in range(1, len(self.trail)):
                pt1 = self.trail[i - 1]
                pt2 = self.trail[i]
                if math.hypot(pt2[0] - pt1[0], pt2[1] - pt1[1]) < 40:
                    pygame.draw.line(surface, self.color, pt1, pt2, self.radius)

        pygame.draw.circle(
            surface, self.color, (int(self.x), int(self.y)), self.radius + 1
        )

    def check_collisions(self, width, height, other_bike, boundary_mode):
        if not self.alive:
            return

        head = (int(self.x), int(self.y))

        if boundary_mode == 'Walls':
            if head[0] < 0 or head[0] > width or head[1] < 0 or head[1] > height:
                self.alive = False
                return

        safe_distance = 10
        if len(self.trail) > safe_distance:
            for pt in self.trail[:-safe_distance]:
                if math.hypot(head[0] - pt[0], head[1] - pt[1]) <= self.radius:
                    self.alive = False
                    return

        for pt in other_bike.trail:
            if math.hypot(head[0] - pt[0], head[1] - pt[1]) <= self.radius:
                self.alive = False
                return

        if math.hypot(head[0] - other_bike.x, head[1] - other_bike.y) <= (
                self.radius * 2
        ):
            self.alive = False


def main():
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Pixel Tron / Infinite Snake")
    clock = pygame.time.Clock()

    font = pygame.font.SysFont(None, 32)
    large_font = pygame.font.SysFont(None, 56)
    title_font = pygame.font.SysFont(None, 64)

    menu_options = [
        ("Game Mode", ["Player vs Player", "Player vs AI"], 1),  # Default to PvAI
        ("AI Difficulty", ["Easy", "Normal", "Hard"], 1),  # Default to Normal
        ("Speed", ["Slow (2.0)", "Normal (3.0)", "Fast (4.5)"], 1),
        ("Boundaries", ["Walls", "Periodic (Wrap)"], 0),
    ]
    selected_menu_index = 0

    game_state = "MENU"
    winner_text = ""
    player1, player2 = None, None

    def start_game():
        nonlocal player1, player2
        mode_choice = menu_options[0][2]  # 0: PvP, 1: PvAI
        ai_diff_choice = menu_options[1][1][menu_options[1][2]]
        diff_choice = menu_options[2][2]
        speeds = [2.0, 3.0, 4.5]
        chosen_speed = speeds[diff_choice]

        is_ai_mode = mode_choice == 1

        player1 = LightBike(
            x=200,
            y=HEIGHT // 2,
            angle=0,
            color=RED,
            controls={'left': pygame.K_a, 'right': pygame.K_d},
            speed=chosen_speed,
        )
        player2 = LightBike(
            x=WIDTH - 200,
            y=HEIGHT // 2,
            angle=180,
            color=BLUE,
            controls={'left': pygame.K_j, 'right': pygame.K_l},
            speed=chosen_speed,
            is_ai=is_ai_mode,
            ai_difficulty=ai_diff_choice,
        )

    while True:
        screen.fill(BLACK)
        keys_pressed = pygame.key.get_pressed()

        # --- EVENT HANDLING ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                if game_state == "MENU":
                    if event.key == pygame.K_UP:
                        selected_menu_index = (selected_menu_index - 1) % len(menu_options)
                    elif event.key == pygame.K_DOWN:
                        selected_menu_index = (selected_menu_index + 1) % len(menu_options)
                    elif event.key == pygame.K_LEFT:
                        opt_name, choices, idx = menu_options[selected_menu_index]
                        menu_options[selected_menu_index] = (
                            opt_name,
                            choices,
                            (idx - 1) % len(choices),
                        )
                    elif event.key == pygame.K_RIGHT:
                        opt_name, choices, idx = menu_options[selected_menu_index]
                        menu_options[selected_menu_index] = (
                            opt_name,
                            choices,
                            (idx + 1) % len(choices),
                        )
                    elif event.key == pygame.K_RETURN:
                        start_game()
                        game_state = "PLAYING"

                elif game_state == "GAME_OVER":
                    if event.key == pygame.K_r:
                        game_state = "MENU"
                    elif event.key == pygame.K_ESCAPE:
                        pygame.quit()
                        sys.exit()

        # --- GAME STATE: MENU ---
        if game_state == "MENU":
            title_surf = title_font.render("TRON: INFINITE SNAKE", True, YELLOW)
            screen.blit(
                title_surf,
                (WIDTH // 2 - title_surf.get_width() // 2, HEIGHT // 6),
            )

            for i, (name, choices, idx) in enumerate(menu_options):
                # Grey out AI difficulty option if PvP mode is selected
                is_disabled = (i == 1) and (menu_options[0][2] == 0)
                color = (
                    GRAY
                    if is_disabled
                    else (YELLOW if i == selected_menu_index else WHITE)
                )
                text = f"{name}: < {choices[idx]} >"
                surf = font.render(text, True, color)
                screen.blit(
                    surf,
                    (
                        WIDTH // 2 - surf.get_width() // 2,
                        HEIGHT // 3 + i * 42,
                    ),
                )

            controls_y = HEIGHT // 2 + 105
            is_ai_mode = menu_options[0][2] == 1
            p1_ctrl = font.render("Player 1 (Red): A / D (Turn)", True, RED)
            p2_ctrl = font.render(
                "Player 2 (Blue): " + ("AI Controlled" if is_ai_mode else "J / L (Turn)"),
                True,
                BLUE,
            )
            screen.blit(
                p1_ctrl, (WIDTH // 2 - p1_ctrl.get_width() // 2, controls_y)
            )
            screen.blit(
                p2_ctrl, (WIDTH // 2 - p2_ctrl.get_width() // 2, controls_y + 32)
            )

            prompt_surf = font.render(
                "Use ARROWS to change settings, ENTER to start", True, GRAY
            )
            screen.blit(
                prompt_surf,
                (
                    WIDTH // 2 - prompt_surf.get_width() // 2,
                    HEIGHT - 50,
                ),
            )

        # --- GAME STATE: PLAYING ---
        elif game_state == "PLAYING":
            boundary_mode = menu_options[3][1][menu_options[3][2]]

            if boundary_mode == "Walls":
                pygame.draw.rect(screen, (50, 50, 70), (0, 0, WIDTH, HEIGHT), 4)

            player1.update(keys_pressed, player2, WIDTH, HEIGHT, boundary_mode)
            player2.update(keys_pressed, player1, WIDTH, HEIGHT, boundary_mode)

            player1.handle_boundaries(WIDTH, HEIGHT, boundary_mode)
            player2.handle_boundaries(WIDTH, HEIGHT, boundary_mode)

            player1.check_collisions(WIDTH, HEIGHT, player2, boundary_mode)
            player2.check_collisions(WIDTH, HEIGHT, player1, boundary_mode)

            player1.draw(screen)
            player2.draw(screen)

            if not player1.alive and not player2.alive:
                game_state = "GAME_OVER"
                winner_text = "It's a Draw!"
            elif not player1.alive:
                game_state = "GAME_OVER"
                winner_text = "Blue (Player 2) Wins!"
            elif not player2.alive:
                game_state = "GAME_OVER"
                winner_text = "Red (Player 1) Wins!"

        # --- GAME STATE: GAME_OVER ---
        elif game_state == "GAME_OVER":
            player1.draw(screen)
            player2.draw(screen)

            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            screen.blit(overlay, (0, 0))

            win_surf = large_font.render(winner_text, True, WHITE)
            restart_surf = font.render("Press 'R' for Menu or ESC to Quit", True, GRAY)

            screen.blit(
                win_surf,
                (
                    WIDTH // 2 - win_surf.get_width() // 2,
                    HEIGHT // 2 - 50,
                ),
            )
            screen.blit(
                restart_surf,
                (
                    WIDTH // 2 - restart_surf.get_width() // 2,
                    HEIGHT // 2 + 20,
                ),
            )

            if keys_pressed[pygame.K_ESCAPE]:
                pygame.quit()
                sys.exit()

        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()