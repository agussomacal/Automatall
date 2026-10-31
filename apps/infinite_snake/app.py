import math
import random
import sys
import pygame

# Initialize Pygame
pygame.init()

# Constants
WIDTH, HEIGHT = 950, 750
FPS = 60

# Colors
BLACK = (10, 10, 15)
WHITE = (240, 240, 240)
GRAY = (120, 120, 120)
HIGHLIGHT_BG = (40, 40, 60)
SELECT_BORDER = (255, 255, 255)

PLAYER_CONFIGS = [
    {"name": "Red", "color": (231, 76, 60), "controls": {"left": pygame.K_a, "right": pygame.K_d}, "key_label": "A/D"},
    {"name": "Blue", "color": (52, 152, 219), "controls": {"left": pygame.K_j, "right": pygame.K_l},
     "key_label": "J/L"},
    {"name": "Green", "color": (46, 204, 113), "controls": {"left": pygame.K_LEFT, "right": pygame.K_RIGHT},
     "key_label": "LEFT/RIGHT"},
    {"name": "Yellow", "color": (241, 196, 15), "controls": {"left": pygame.K_f, "right": pygame.K_g},
     "key_label": "F/G"},
    {"name": "Purple", "color": (155, 89, 182), "controls": {"left": pygame.K_c, "right": pygame.K_v},
     "key_label": "C/V"},
    {"name": "Orange", "color": (230, 126, 34), "controls": {"left": pygame.K_n, "right": pygame.K_m},
     "key_label": "N/M"},
]


class LightBike:

    def __init__(self, x, y, angle, config, speed, team_id, is_ai=False, ai_difficulty="Normal"):
        self.x = float(x)
        self.y = float(y)
        self.angle = angle  # in degrees
        self.speed = speed
        self.turn_speed = 3.5
        self.name = config["name"]
        self.color = config["color"]
        self.controls = config["controls"]
        self.team_id = team_id
        self.trail = []
        self.alive = True
        self.radius = 3
        self.frame_count = 0
        self.spawn_grace_period = 65  # Generous grace period for multi-player spawns

        # AI Properties
        self.is_ai = is_ai
        self.ai_difficulty = ai_difficulty
        self.ai_timer = 0
        self.ai_target_turn = 0

        if self.is_ai:
            if ai_difficulty == "Easy":
                self.vision_range = 60
                self.reaction_delay = 8
                self.error_chance = 0.12
            elif ai_difficulty == "Normal":
                self.vision_range = 100
                self.reaction_delay = 3
                self.error_chance = 0.02
            else:  # Hard
                self.vision_range = 150
                self.reaction_delay = 1
                self.error_chance = 0.0

    def update(self, keys_pressed, all_bikes, width, height, boundary_mode):
        if not self.alive:
            return

        if self.spawn_grace_period > 0:
            self.spawn_grace_period -= 1

        if self.is_ai:
            self.update_ai(all_bikes, width, height, boundary_mode)
            if self.ai_target_turn < 0:
                self.angle -= self.turn_speed
            elif self.ai_target_turn > 0:
                self.angle += self.turn_speed
        else:
            if self.controls and keys_pressed[self.controls['left']]:
                self.angle -= self.turn_speed
            if self.controls and keys_pressed[self.controls['right']]:
                self.angle += self.turn_speed

        self.frame_count += 1
        cycle = self.frame_count % 180
        is_leaving_trail = cycle < 145

        if is_leaving_trail and self.spawn_grace_period == 0:
            self.trail.append((int(self.x), int(self.y)))

        rad = math.radians(self.angle)
        self.x += self.speed * math.cos(rad)
        self.y += self.speed * math.sin(rad)

    def check_ray(self, angle_offset, width, height, all_bikes, boundary_mode):
        rad = math.radians(self.angle + angle_offset)
        step = 8
        for d in range(step, int(self.vision_range), step):
            cx = self.x + d * math.cos(rad)
            cy = self.y + d * math.sin(rad)

            if boundary_mode == 'Walls':
                if cx < 10 or cx > width - 10 or cy < 10 or cy > height - 10:
                    return True

            for bike in all_bikes:
                if bike == self:
                    continue
                if bike.spawn_grace_period > 0 or self.spawn_grace_period > 0:
                    continue

                for pt in bike.trail:
                    if math.hypot(cx - pt[0], cy - pt[1]) <= self.radius + 3:
                        return True
                if math.hypot(cx - bike.x, cy - bike.y) <= self.radius * 5:
                    return True

        return False

    def update_ai(self, all_bikes, width, height, boundary_mode):
        self.ai_timer += 1
        if self.ai_timer < self.reaction_delay:
            return
        self.ai_timer = 0

        if random.random() < self.error_chance:
            self.ai_target_turn = random.choice([-1, 0, 1])
            return

        # Expanded 360-degree awareness: Forward, Diagonals, and Flanks (Sides)
        fwd_danger = self.check_ray(0, width, height, all_bikes, boundary_mode)
        left_diag = self.check_ray(-45, width, height, all_bikes, boundary_mode)
        right_diag = self.check_ray(45, width, height, all_bikes, boundary_mode)
        left_flank = self.check_ray(-90, width, height, all_bikes, boundary_mode)
        right_flank = self.check_ray(90, width, height, all_bikes, boundary_mode)

        # Decision logic prioritizing side-threat evasion and open space
        if not fwd_danger and not left_diag and not right_diag:
            self.ai_target_turn = 0  # Path is completely clear ahead
        else:
            # If something is threatening us from the left flank or diagonal, turn right
            if left_diag or left_flank:
                self.ai_target_turn = 1
            # If something is threatening us from the right flank or diagonal, turn left
            elif right_diag or right_flank:
                self.ai_target_turn = -1
            else:
                # General obstacle ahead, choose side with less immediate danger
                score_left = 0 if left_diag else 1
                score_right = 0 if right_diag else 1
                if score_left > score_right:
                    self.ai_target_turn = -1
                elif score_right > score_left:
                    self.ai_target_turn = 1
                else:
                    self.ai_target_turn = random.choice([-1, 1])

    def handle_boundaries(self, width, height, boundary_mode):
        if boundary_mode == 'Periodic (Wrap)':
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

        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.radius + 1)

    def check_collisions(self, width, height, all_bikes, boundary_mode):
        if not self.alive or self.spawn_grace_period > 0:
            return

        head = (int(self.x), int(self.y))

        if boundary_mode == 'Walls':
            if head[0] < 0 or head[0] > width or head[1] < 0 or head[1] > height:
                self.alive = False
                return

        safe_distance = 15
        if len(self.trail) > safe_distance:
            for pt in self.trail[:-safe_distance]:
                if math.hypot(head[0] - pt[0], head[1] - pt[1]) <= self.radius:
                    self.alive = False
                    return

        for bike in all_bikes:
            if bike == self or bike.spawn_grace_period > 0:
                continue
            for pt in bike.trail:
                if math.hypot(head[0] - pt[0], head[1] - pt[1]) <= self.radius:
                    self.alive = False
                    return
            if math.hypot(head[0] - bike.x, head[1] - bike.y) <= (self.radius * 2):
                self.alive = False
                return


def main():
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Pixel Tron / Infinite Snake - Multiplayer")
    clock = pygame.time.Clock()

    font = pygame.font.SysFont(None, 24)
    large_font = pygame.font.SysFont(None, 48)
    title_font = pygame.font.SysFont(None, 46)

    player_slots = [
        {"type": "Human", "team": "Team 1"},
        {"type": "AI (Normal)", "team": "Team 2"},
        {"type": "AI (Hard)", "team": "Team 3"},
        {"type": "Disabled", "team": "Team 4"},
        {"type": "Disabled", "team": "Team 1"},
        {"type": "Disabled", "team": "Team 2"},
    ]

    type_options = ["Disabled", "Human", "AI (Easy)", "AI (Normal)", "AI (Hard)"]
    team_options = ["Team 1", "Team 2", "Team 3", "Team 4"]

    menu_options = [
        ("Speed", ["Slow (2.0)", "Normal (3.0)", "Fast (4.5)"], 1),
        ("Boundaries", ["Walls", "Periodic (Wrap)"], 0),
    ]
    selected_menu_index = 0

    game_state = "MENU"
    winner_text = ""
    bikes = []

    def start_game():
        nonlocal bikes
        bikes = []
        speed_choices = [2.0, 3.0, 4.5]
        chosen_speed = speed_choices[menu_options[0][2]]

        active_slots = []
        for i, slot in enumerate(player_slots):
            if slot["type"] != "Disabled":
                active_slots.append((i, slot))

        num_active = len(active_slots)
        if num_active < 2:
            active_slots = [(0, {"type": "Human", "team": "Team 1"}), (1, {"type": "AI (Normal)", "team": "Team 2"})]
            num_active = len(active_slots)

        spawn_radius = min(WIDTH, HEIGHT) * 0.32

        for index, (slot_idx, slot_data) in enumerate(active_slots):
            angle = (360 / num_active) * index
            rad = math.radians(angle)
            x = WIDTH // 2 + spawn_radius * math.cos(rad)
            y = HEIGHT // 2 + spawn_radius * math.sin(rad)

            # Tangential offset heading so bikes fan out smoothly
            facing_angle = (angle + 110) % 360

            status = slot_data["type"]
            is_ai = status.startswith("AI")
            ai_diff = status.split("(")[1].replace(")", "") if is_ai else "Normal"
            team_id = team_options.index(slot_data["team"])

            bikes.append(
                LightBike(
                    x=x,
                    y=y,
                    angle=facing_angle,
                    config=PLAYER_CONFIGS[slot_idx],
                    speed=chosen_speed,
                    team_id=team_id,
                    is_ai=is_ai,
                    ai_difficulty=ai_diff,
                )
            )

    while True:
        screen.fill(BLACK)
        keys_pressed = pygame.key.get_pressed()

        total_slots_rows = len(player_slots)
        total_menu_items = len(menu_options) + (total_slots_rows * 2)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                if game_state == "MENU":
                    if event.key == pygame.K_UP:
                        selected_menu_index = (selected_menu_index - 1) % total_menu_items
                    elif event.key == pygame.K_DOWN:
                        selected_menu_index = (selected_menu_index + 1) % total_menu_items
                    elif event.key == pygame.K_LEFT:
                        if selected_menu_index < len(menu_options):
                            opt_name, choices, idx = menu_options[selected_menu_index]
                            menu_options[selected_menu_index] = (opt_name, choices, (idx - 1) % len(choices))
                        else:
                            slot_row = (selected_menu_index - len(menu_options)) // 2
                            sub_col = (selected_menu_index - len(menu_options)) % 2
                            if sub_col == 0:
                                curr_val = player_slots[slot_row]["type"]
                                curr_idx = type_options.index(curr_val)
                                player_slots[slot_row]["type"] = type_options[(curr_idx - 1) % len(type_options)]
                            else:
                                curr_val = player_slots[slot_row]["team"]
                                curr_idx = team_options.index(curr_val)
                                player_slots[slot_row]["team"] = team_options[(curr_idx - 1) % len(team_options)]
                    elif event.key == pygame.K_RIGHT:
                        if selected_menu_index < len(menu_options):
                            opt_name, choices, idx = menu_options[selected_menu_index]
                            menu_options[selected_menu_index] = (opt_name, choices, (idx + 1) % len(choices))
                        else:
                            slot_row = (selected_menu_index - len(menu_options)) // 2
                            sub_col = (selected_menu_index - len(menu_options)) % 2
                            if sub_col == 0:
                                curr_val = player_slots[slot_row]["type"]
                                curr_idx = type_options.index(curr_val)
                                player_slots[slot_row]["type"] = type_options[(curr_idx + 1) % len(type_options)]
                            else:
                                curr_val = player_slots[slot_row]["team"]
                                curr_idx = team_options.index(curr_val)
                                player_slots[slot_row]["team"] = team_options[(curr_idx + 1) % len(team_options)]
                    elif event.key == pygame.K_RETURN:
                        start_game()
                        game_state = "PLAYING"

                elif game_state == "GAME_OVER":
                    if event.key == pygame.K_r:
                        game_state = "MENU"
                    elif event.key == pygame.K_ESCAPE:
                        pygame.quit()
                        sys.exit()

        # --- MENU RENDER WITH COLOR SWATCHES & CONTROL HINTS ---
        if game_state == "MENU":
            title_surf = title_font.render("TRON: INFINITE SNAKE", True, WHITE)
            screen.blit(title_surf, (WIDTH // 2 - title_surf.get_width() // 2, 15))

            y_offset = 60
            for i, (name, choices, idx) in enumerate(menu_options):
                is_selected = (i == selected_menu_index)
                text = f"{name}: < {choices[idx]} >"

                box_width, box_height = 400, 30
                box_x = WIDTH // 2 - box_width // 2
                box_y = y_offset

                if is_selected:
                    pygame.draw.rect(screen, HIGHLIGHT_BG, (box_x, box_y, box_width, box_height))
                    pygame.draw.rect(screen, SELECT_BORDER, (box_x, box_y, box_width, box_height), 2)

                surf = font.render(text, True, WHITE)
                screen.blit(surf, (WIDTH // 2 - surf.get_width() // 2, y_offset + 6))
                y_offset += 38

            y_offset += 5
            header_surf = font.render("--- Player Configuration ---", True, GRAY)
            screen.blit(header_surf, (WIDTH // 2 - header_surf.get_width() // 2, y_offset))
            y_offset += 26

            for i, slot in enumerate(player_slots):
                type_menu_idx = len(menu_options) + (i * 2)
                team_menu_idx = len(menu_options) + (i * 2) + 1

                is_type_selected = (type_menu_idx == selected_menu_index)
                is_team_selected = (team_menu_idx == selected_menu_index)

                row_start_x = WIDTH // 2 - 275

                # 1. Draw Color Swatch Circle
                pygame.draw.circle(screen, PLAYER_CONFIGS[i]["color"], (row_start_x + 10, y_offset + 13), 7)

                # 2. Draw Type Box
                type_box_w, type_box_h = 265, 26
                type_box_x = row_start_x + 25
                type_box_y = y_offset

                if is_type_selected:
                    pygame.draw.rect(screen, HIGHLIGHT_BG, (type_box_x, type_box_y, type_box_w, type_box_h))
                    pygame.draw.rect(screen, SELECT_BORDER, (type_box_x, type_box_y, type_box_w, type_box_h), 2)

                type_val = slot['type']
                if type_val == "Human":
                    type_text = f"P{i + 1}: Human ({PLAYER_CONFIGS[i]['key_label']})"
                else:
                    type_text = f"P{i + 1}: {type_val}"

                type_surf = font.render(f"< {type_text} >", True, WHITE)
                screen.blit(type_surf, (type_box_x + 8, type_box_y + 4))

                # 3. Draw Team Box
                team_box_w, team_box_h = 160, 26
                team_box_x = row_start_x + 300
                team_box_y = y_offset

                if is_team_selected:
                    pygame.draw.rect(screen, HIGHLIGHT_BG, (team_box_x, team_box_y, team_box_w, team_box_h))
                    pygame.draw.rect(screen, SELECT_BORDER, (team_box_x, team_box_y, team_box_w, team_box_h), 2)

                team_text = f"Team: < {slot['team']} >"
                team_surf = font.render(team_text, True, WHITE)
                screen.blit(team_surf, (team_box_x + 10, team_box_y + 4))

                y_offset += 32

            prompt_surf = font.render("Use UP/DOWN to navigate, LEFT/RIGHT to change, ENTER to start", True, GRAY)
            screen.blit(prompt_surf, (WIDTH // 2 - prompt_surf.get_width() // 2, HEIGHT - 30))

        # --- GAMEPLAY RENDER ---
        elif game_state == "PLAYING":
            boundary_mode = menu_options[1][1][menu_options[1][2]]

            if boundary_mode == "Walls":
                pygame.draw.rect(screen, (50, 50, 70), (0, 0, WIDTH, HEIGHT), 4)

            for bike in bikes:
                bike.update(keys_pressed, bikes, WIDTH, HEIGHT, boundary_mode)
                bike.handle_boundaries(WIDTH, HEIGHT, boundary_mode)

            for bike in bikes:
                bike.check_collisions(WIDTH, HEIGHT, bikes, boundary_mode)
                bike.draw(screen)

            alive_bikes = [b for b in bikes if b.alive]
            alive_teams = set(b.team_id for b in alive_bikes)

            if len(alive_teams) <= 1:
                game_state = "GAME_OVER"
                if len(alive_teams) == 1:
                    winning_team_id = list(alive_teams)[0]
                    winner_text = f"Team {winning_team_id + 1} Wins!"
                else:
                    winner_text = "It's a Draw!"

        # --- GAME OVER RENDER ---
        elif game_state == "GAME_OVER":
            for bike in bikes:
                bike.draw(screen)

            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            screen.blit(overlay, (0, 0))

            win_surf = large_font.render(winner_text, True, WHITE)
            restart_surf = font.render("Press 'R' for Menu or ESC to Quit", True, GRAY)

            screen.blit(win_surf, (WIDTH // 2 - win_surf.get_width() // 2, HEIGHT // 2 - 40))
            screen.blit(restart_surf, (WIDTH // 2 - restart_surf.get_width() // 2, HEIGHT // 2 + 20))

            if keys_pressed[pygame.K_ESCAPE]:
                pygame.quit()
                sys.exit()

        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()