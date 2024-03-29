#!/usr/bin/env python3
# Python 3.6
import hlt
from hlt import constants
from hlt.positionals import Direction, Position
import logging
from collections import defaultdict, OrderedDict, namedtuple, deque
import math

global game


def get_path_halite_cost(start, end, game_map):
    cost = 0
    moves = game_map.get_unsafe_moves(start, end)
    curr = start
    # TODO: path should be optimised - direct isn't always the best, A*?
    while moves:
        cost += game_map[curr].halite_amount * .1
        moves.sort(key=lambda m: game_map[curr.directional_offset(m)].halite_amount)
        # assume we also travel along the path with least halite
        curr = game_map.normalize(curr.directional_offset(moves[0]))
        moves = game_map.get_unsafe_moves(curr, end)
    return cost * 1


def get_df():
    if game.turn_number < 100:
        df = .95
    elif game.turn_number < 300:
        df = .97
    else:
        df = .99
    return df


def get_all_map_cells(game_map):
    return [game_map[Position(j, i)] for i in range(0, game_map.height) for j in range(0, game_map.width)]


def get_halite_positions_by_path_cost(game_map, me, map_cells, halite_threshold, descending=False, extra=None):
    full_coord = map_cells
    # full_coord = [get_surrounding_cells(game_map, p, int(game_map.height/3)) for
    #              p in get_dropoff_positions(me)]
    # full_coord = [c for fcl in full_coord for c in fcl]
    dropoffs = get_dropoff_positions(me)
    for dropoff in dropoffs:
        full_coord.remove(game_map[dropoff])

    df = get_df()
    full_coord.sort(key=lambda x: (x.halite_amount - halite_threshold - get_path_halite_cost(me.shipyard.position, x.position, game_map)) * df ** (2 * game_map.calculate_distance(
        me.shipyard.position, x.position)), reverse=descending)

    # TODO: linear isn't that bad
    # full_coord.sort(key=lambda x: (x.halite_amount - halite_threshold - get_path_halite_cost(me.shipyard.position, x.position, game_map))/(2 * game_map.calculate_distance(me.shipyard.position, x.position)), reverse=descending)
    # TODO: sigmoid
    #full_coord.sort(key=lambda x: (x.halite_amount - halite_threshold - get_path_halite_cost(me.shipyard.position, x.position, game_map))/
    #                              (game_map.calculate_distance(me.shipyard.position, x.position)**1.5), reverse=descending)
    # TODO: need to add lower & upper bound if we want to optimise with current time value
    # full_coord.sort(key=lambda x: x.halite_amount - halite_threshold/4 * 2 * game_map.calculate_distance(
    #                get_nearest_dropoff(game_map, me, x.position), x.position), reverse=descending)
    return [c.position for c in full_coord]  # popped


def get_halite_cells(game_map, me, map_cells, halite_threshold, descending=False, extra=None):
    full_coord = map_cells
    # full_coord = [get_surrounding_cells(game_map, p, int(game_map.height/3)) for
    #              p in get_dropoff_positions(me)]
    # full_coord = [c for fcl in full_coord for c in fcl]
    dropoffs = get_dropoff_positions(me)
    for dropoff in dropoffs:
        full_coord.remove(game_map[dropoff])

    df = get_df()
    # TODO: path cost timed out
    full_coord.sort(key=lambda x: (x.halite_amount - halite_threshold) * df ** (2 * game_map.calculate_distance(
        get_nearest_dropoff(game_map, me, x.position, extra), x.position)), reverse=descending)
    # TODO: need to add lower & upper bound if we want to optimise with current time value
    # full_coord.sort(key=lambda x: x.halite_amount - halite_threshold/4 * 2 * game_map.calculate_distance(
    #                get_nearest_dropoff(game_map, me, x.position), x.position), reverse=descending)
    # TODO: problem was ships went too far off, try own quadrant/limit the search radius?
    # full_coord.sort(key=lambda x: (get_halite_priority(x.halite_amount),
    #                            1. / (game_map.calculate_distance(get_nearest_dropoff(game_map, me, x.position), x.position) + 1)),  # origin+1
    #                reverse=descending)
    return full_coord  # popped


def get_surrounding_cells(game_map, current_pos, radius):
    coords = [game_map[game_map.normalize(Position(i, j))]
              for i in range(current_pos.x - radius, current_pos.x + radius)
              for j in range(current_pos.y - radius, current_pos.y + radius)]
    return coords


def get_surrounding_halite(game_map, current_pos, radius=6):
    coords = get_cells_within_distance(game_map, current_pos, radius)
    total = sum([c.halite_amount for c in coords])
    return total


def get_unextracted_halite(map_cells):
    cells = map_cells
    total = sum([c.halite_amount for c in cells])
    return total


def get_possible_paths(origin, target, game_map, path, out_possible_paths, length=3):
    if len(path) == length:
        out_possible_paths.append(path)
    else:
        moves = game_map.get_unsafe_moves(origin, target)
        if moves:
            for m in moves:
                new_origin = game_map.normalize(origin.directional_offset(m))
                new_path = path + [new_origin]
                get_possible_paths(new_origin, target, game_map, new_path, out_possible_paths)
        else:
            # arrived at destination
            out_possible_paths.append(path)
            return


def equivalent_move(origin, target, game_map):
    return next((m for m in Direction.get_all_cardinals() if game_map.normalize(origin.directional_offset(m)) == target),
                Direction.Still)


def get_possible_moves(target, ship, game_map, me):
    # No need to normalize destination, since get_unsafe_moves does that
    if ship.halite_amount >= .1 * game_map[ship.position].halite_amount:
        possible_paths = []
        get_possible_paths(ship.position, target, game_map, [], possible_paths)
        possible_paths.sort(key=lambda p: sum([game_map[pos].halite_amount for pos in p]))
        possible_moves = [equivalent_move(ship.position, path[0], game_map) for path in possible_paths if path]
        # possible_moves = game_map.get_unsafe_moves(ship.position, target)
        # possible_moves.sort(key=lambda x: game_map[ship.position.directional_offset(x)].halite_amount)
        return possible_moves
    else:
        logging.info("Ship {} has not enough halite to move anywhere.".format(ship.id))
        return []


def get_dropoff_positions(me, extra=None):
    dropoffs = [d.position for d in me.get_dropoffs()]
    dropoffs.append(me.shipyard.position)
    if extra:
        dropoffs.append(extra)  # hack dropoff going to be build
    return dropoffs


def get_nearest_dropoff(map, me, position, extra=None):
    dropoffs = sorted(get_dropoff_positions(me, extra), key=lambda x: map.calculate_distance(position, x))
    return dropoffs[0]


def halite_priority(amount):
    # basically set rough priority for sorting
    if amount < 30:
        return -2
    if amount < 75:
        return -1

    elif amount < 150:
        return 0
    elif amount < 250:
        return 1
    elif amount < 400:
        return 2
    elif amount < 500:
        return 3
    elif amount < 600:
        return 4
    elif amount < 700:
        return 5
    elif amount < 800:
        return 6
    elif amount < 900:
        return 7
    elif amount < 1200:
        return 8
    else:
        return 9


def round_down(x):
    return math.floor(x / 100) * 100


def try_get_halite_target_nearby(game_map, ship, nearest_dropoff, ship_targets, min_halite, radius=2):
    logging.info("Ship {} searching nearby targets around {}".format(ship.id, ship.position))
    new_targets = get_cells_within_distance(game_map, ship.position, radius)
    new_targets = [t for t in new_targets if t.halite_amount > min_halite]
    new_targets.sort(key=lambda x: (halite_priority(x.halite_amount),
                                    1. / (game_map.calculate_distance(nearest_dropoff, x.position) + 1)),  # origin+1
                     reverse=True)

    new_target = next((t.position for t in new_targets if t.position not in ship_targets.values()), nearest_dropoff)
    logging.info('Ship {} finished at {}, moving to nearby target {}'
                 .format(ship.id, ship.position, new_target))
    return new_target


def get_cells_within_distance(game_map, origin, radius):
    res = []
    for i in range(1, radius + 1):
        int_pairs = [(j, i - j) for j in range(i)]
        for pair in int_pairs:
            res.extend([(pair[0], pair[1]), (-pair[0], pair[1]), (pair[0], -pair[1]), (-pair[0], -pair[1])])
        int_pairs = [(i - j, j) for j in range(i)]
        for pair in int_pairs:
            res.extend([(pair[0], pair[1]), (-pair[0], pair[1]), (pair[0], -pair[1]), (-pair[0], -pair[1])])
    # TODO: turn to hash string and turn back to make it more efficient
    res = [game_map[origin]] + [game_map[Position(origin.x + r[0], origin.y + r[1])] for r in res]
    return res


def nearest_halite_cell_with_x(game_map, origin, ship_targets, min_halite, max_radius=2, default_target=None):
    logging.info("Ship {} get_nearest_halite_cell_with_x {}".format(ship.id, ship.position))
    targets = get_cells_within_distance(game_map, origin, max_radius)
    targets.sort(key=lambda t: (game_map.calculate_distance(t.position, origin), 1 / (t.halite_amount + 1)))
    return next((t.position for t in targets if t.halite_amount > min_halite and
                 t.position not in ship_targets.values() and not t.is_occupied), default_target)


def pos_to_hash_key(position):
    if position:
        return str(position.x) + ',' + str(position.y)
    else:
        return None


def hash_key_to_pos(key):
    xy = key.split(',')
    return Position(int(xy[0]), int(xy[1]))


def command_to_direction(command):
    if command == 'n':
        return Direction.North
    if command == 's':
        return Direction.South
    if command == 'e':
        return Direction.East
    if command == 'w':
        return Direction.West
    if command == 'o':
        return Direction.Still


def execute_path(path, command_dict, game_map):
    logging.info("Executing path: {}".format(path))
    ships = [game_map[pos.directional_offset(Direction.invert(move))].ship
             for pos, move in path]
    for ship in ships:
        if ship:
            game_map[ship.position].ship = None

    moves = [m for pos, m in path]
    for ship, move in zip(ships, moves):
        logging.info('{}{}'.format(ship, move))
        if ship:
            new_pos = game_map.normalize(ship.position.directional_offset(move))
            if ship.id not in command_dict:
                logging.info("Ship {} will move {} to {}".format(ship.id, move, new_pos))
                command_dict[ship.id] = ship.move(move)
                game_map[new_pos].mark_unsafe(ship)
            else:
                # TODO: (allow override if it's better), this path is not being hit currently
                logging.info("TEST: Ship {} will move {} to {}".format(ship.id, move, new_pos))
                # assume we always want to minimise halite
                original_move = command_to_direction(command_dict[ship.id].split(' ')[2])
                original_target = game_map.normalize(ship.position.directional_offset(original_move))
                logging.info("TEST: Ship {} was going to move {} to {}".format(ship.id, original_move, original_target))
                if game_map[original_target].halite_amount > game_map[new_pos].halite_amount:
                    logging.info("OVERRIDING!")
                    command_dict[ship.id] = ship.move(move)
                    game_map[new_pos].mark_unsafe(ship)
                    game_map[original_target].ship = None


def resolve_moves_recursive(path, ship_id, graph, command_dict, game_map):
    if ship_id in command_dict:
        return True  # ship has planned move already

    ship_plan = graph[ship_id]
    # Hacking to ensure we use free cells first
    for t_pos, t_move in ship_plan.to:
        if not game_map[t_pos].is_occupied:
            # Path viable
            path.append((t_pos, t_move))
            logging.info("Path found: {}".format(path))
            execute_path(path, command_dict, game_map)
            return True

    for t_pos, t_move in ship_plan.to:
        if game_map[t_pos].ship.id in command_dict:
            return False  # path is being used next turn (rmb reg move will clear cell so should)

        if pos_to_hash_key(t_pos) in [pos_to_hash_key(p[0]) for p in path]:
            # encountered cycle, execute the cycle only, scrap the remaining chain
            logging.info("original path {}".format(path))
            path.append((t_pos, t_move))
            logging.info("appending {} and {} as the last step of path".format(t_pos, t_move))
            cycle_start_idx = next(i for i, p in enumerate(path) if pos_to_hash_key(p[0]) == pos_to_hash_key(t_pos))
            for x in range(0, cycle_start_idx + 1):
                path.pop(0)
                logging.info("popped at {}".format(x))
            logging.info("Cyclic Path found: {}".format(path))
            execute_path(path, command_dict, game_map)
            return True
        else:
            # keep searching, DFSs
            next_ship_id = game_map[t_pos].ship.id
            new_path = path.copy()
            new_path.append((t_pos, t_move))
            found = resolve_moves_recursive(new_path, next_ship_id, graph, command_dict, game_map)
            if found:
                return True


def register_move(ship, move, command_dict, game_map):
    new_pos = ship.position.directional_offset(move)
    logging.info("Ship {} will move {} to {}".format(ship.id, move, new_pos))
    command_dict[ship.id] = ship.move(move)
    game_map[ship.position].ship = None
    game_map[new_pos].mark_unsafe(ship)


def get_opponents_position(map_cells, me):
    cells = map_cells
    ship_position_mapping = {cell.ship.id: cell.ship.position for cell in cells
                             if (cell.ship is not None and not me.has_ship(cell.ship.id))}
    return ship_position_mapping


def predict_opponents_target(game_map, prev_pos, curr_pos):
    opponents_targets = {}
    for opponent_ship_id in prev_pos.keys():
        if opponent_ship_id not in curr_pos:
            continue  # ship crashed
        prev = prev_pos[opponent_ship_id]
        curr = curr_pos[opponent_ship_id]
        move = next((m for m in Direction.get_all_cardinals() if game_map.normalize(prev.directional_offset(m)) == curr),
                    Direction.Still)
        opponents_targets[opponent_ship_id] = game_map.normalize(curr.directional_offset(move))

    return opponents_targets


def get_all_dropoffs_including_enemies(game_map):
    cells = [game_map[Position(j, i)] for i in range(0, game_map.height) for j in range(0, game_map.width)
             if game_map[Position(j, i)].has_structure]
    return cells


def get_cells_of_our_quadrant(game_map, me, is_4p):
    w = game_map.width
    w_half = int(game_map.width / 2)
    h = game_map.height
    h_half = int(game_map.height / 2)

    if is_4p:
        if me.shipyard.position.x < game_map.width / 2:
            if me.shipyard.position.y < game_map.height / 2:
                return [game_map[Position(j, i)] for i in range(0, h_half) for j in range(0, w_half)]
            else:
                return [game_map[Position(j, i)] for i in range(h_half, h) for j in range(0, w_half)]
        else:
            if me.shipyard.position.y < game_map.height / 2:
                return [game_map[Position(j, i)] for i in range(0, h_half) for j in range(w_half, w)]
            else:
                return [game_map[Position(j, i)] for i in range(h_half, h) for j in range(w_half, w)]
    else:
        if me.shipyard.position.x < game_map.width / 2:
            return [game_map[Position(j, i)] for i in range(0, h) for j in range(0, w_half)]
        else:
            return [game_map[Position(j, i)] for i in range(0, h) for j in range(w_half, w)]


def dropoff_candidate_is_valid(game_map, candidate):
    dropoffs = get_all_dropoffs_including_enemies(game_map)
    #if IS_4P:
    near_dropoff = False
    for dropoff in dropoffs:
        if game_map.calculate_distance(dropoff.position, candidate) < DROPOFF_MIN_DISTANCE:
            near_dropoff = True
            break
    return not near_dropoff
    #else:
    #    return False if candidate in [d.position for d in dropoffs] else True


def get_dropoff_candidate(game_map, me, is_4p):
    positions = [c.position for c in get_cells_of_our_quadrant(game_map, me, is_4p)]
    dropoffs = get_all_dropoffs_including_enemies(game_map)
    candidates = []
    for p in positions:
        near_dropoff = False
        for dropoff in dropoffs:
            if game_map.calculate_distance(dropoff.position, p) < DROPOFF_MIN_DISTANCE:
                near_dropoff = True
                break
        if not near_dropoff:
            candidates.append(p)

    if not candidates:
        return None

    max_amount = 0
    candidate = None
    for p in candidates:
        amount = get_surrounding_halite(game_map, p, radius=6)
        if amount > max_amount:
            max_amount = amount
            candidate = p

    # for the first dropoff, shift slightly closer to shipyard.
    # TODO: shifting may not actually work because visitors may not be coming from shipyard
    # if len(me.get_dropoffs()) == 0:
    #    logging.info("DEBUG OK")
    #    for i in range(3):
    #        candidate = candidate.directional_offset(game_map.get_unsafe_moves(candidate, me.shipyard.position)[0])

    return candidate if max_amount > DROPOFF_HALITE_THRESHOLD else None


def get_ship_remaining_turns(me, game_map, ship, halite_threshold):
    # assuming it's already at target!
    available = game_map[ship.position].halite_amount
    storage = ship.halite_amount
    am_inspired = is_inspired(me, game_map, ship)
    turns = 0
    while available > halite_threshold and storage <= 1000:
        turns += 1
        available -= available * .25
        storage += available * (.75 if am_inspired else .25)
    return turns


def get_enemy_ship_count(enemy_dict):
    enemy_ship_count = sum([len(enemy.get_ships()) for enemy in enemy_dict.values()])
    logging.info("Enemy ship count: {}".format(enemy_ship_count))
    if IS_4P:
        enemy_ship_count /= 3
    return enemy_ship_count


def enemy_within_distance(me, game_map, origin, distance):
    cells = get_cells_within_distance(game_map, origin, distance)
    enemies = [c for c in cells if c.ship and not me.has_ship(c.ship.id)]
    return enemies


def ally_within_distance(me, game_map, origin, distance):
    cells = get_cells_within_distance(game_map, origin, distance)
    allies = [c for c in cells if c.ship and me.has_ship(c.ship.id)]
    return allies


def update_ship_halite_amount(ships):
    return {ship.id: ship.halite_amount for ship in ships}


def is_inspired(me, game_map, ship):
    return len(enemy_within_distance(me, game_map, ship.position, 4)) >= 2


mapsize_turn = {
    32: 401,
    40: 426,
    48: 451,
    56: 476,
    64: 501
}

ship_targets = {}  # Final goal of the ship
stalling_ships = {}  # ships that stalled the previous round
ship_planned_moves = {}  # storing planned moves
halite_collection_rate = deque(maxlen=10)  # to track average halite collected
ship_prev_halite_amount = {}  # to track halite amount previous turn, hacky
ship_last_dropoff_turn = {}  # to track when it last visited dropoff (to track collection rate)

enemies_ship_prev_pos = {}
enemies_ship_current_pos = {}
enemies_predicted_targets = {}

game = hlt.Game()
game_map = game.game_map
me = game.me
MAX_TURN = mapsize_turn[game_map.height]

game.ready("Higgs")
logging.info('Bot: Higgs.')

ShipPlan = namedtuple('ShipPlan', 'ship to')
ship_to_be_dropoff_id = None
next_dropoff_candidate = None

global IS_4P
IS_4P = len(game.players) == 4

# SETTINGS
TURNS_TO_RECALL = 3
DROPOFF_HALITE_THRESHOLD = 3500
DROPOFF_MIN_DISTANCE = int(game_map.height / (3.5 if IS_4P else 2.75))
DROPOFF_MIN_SHIP = {1: 20, 2: 35, 3: 50, 4: 60, 5: 70}
DROPOFF_MAX_NO = 4  # not including shipyard
DROPOFF_MAX_TURN = 250  # from final turn
SHIP_MAX_TURN = 200  # from final turn
SHIP_HOLD_AMOUNT = constants.MAX_HALITE * (.75 if (IS_4P and game_map.height <= 48) else .9)
STALLING_THRESHOLD_SOFT = 200  # stall one round
STALLING_THRESHOLD_HARD = 300  # stall till cell has less than this
HALITE_START_COLLECT_RATIO = .8  # as percentage of mean
HALITE_END_COLLECT_RATIO = .5  # as percentage of mean
NEARBY_SEARCH_RADIUS_EARLY = 2
NEARBY_SEARCH_RADIUS_LATE = 4
BIG_SEARCH_RADIUS = 6
LATE_GAME_TURN = 350

map_cells_cache = get_all_map_cells(game_map)  # cache

while True:
    game.update_frame()
    me = game.me
    enemies = {p_id: p for p_id, p in game.players.items() if p_id != me.id}
    enemy_ship_count = get_enemy_ship_count(enemies)
    game_map = game.game_map

    graph = {}
    target_count = defaultdict(int)
    command_queue = []
    command_dict = {}

    map_cells_cache = get_all_map_cells(game_map)  # cache
    enemies_ship_prev_pos = enemies_ship_current_pos
    enemies_ship_current_pos = get_opponents_position(map_cells_cache, me)
    enemies_predicted_targets = predict_opponents_target(game_map, enemies_ship_prev_pos, enemies_ship_current_pos)

    ship_prev_halite_amount = update_ship_halite_amount(me.get_ships())

    remaining_halite = get_unextracted_halite(map_cells_cache)
    mean_halite = remaining_halite / game_map.height / game_map.height
    IS_LATE_GAME = game.turn_number > LATE_GAME_TURN and mean_halite < 70
    halite_threshold_start_collect = mean_halite * HALITE_START_COLLECT_RATIO  # avg_rate*8
    halite_threshold_end_collect = mean_halite * HALITE_END_COLLECT_RATIO  # avg_rate*4
    search_radius = NEARBY_SEARCH_RADIUS_LATE if IS_LATE_GAME else NEARBY_SEARCH_RADIUS_EARLY

    logging.info("Remaining halite: {}, ({} on average)".format(remaining_halite, mean_halite))

    logging.info('#-2 Clearing targets of crashed ships')
    if me.get_ships() is not None:
        crashed_ships = [s_id for s_id in ship_targets if not me.has_ship(s_id)]
        for cs in crashed_ships:
            logging.info("Removing Ship {}".format(cs))
            del ship_targets[cs]
        if ship_to_be_dropoff_id and not me.has_ship(ship_to_be_dropoff_id):
            logging.info("Ship {} was a dropoff candidate but has sunk!".format(ship_to_be_dropoff_id))
            ship_to_be_dropoff_id = None

    logging.info("#-1 Check if dropoff can be built")
    ready_to_build_dropoff = False
    building_dropoff_this_round = False
    hack_dropoff = None
    if ship_to_be_dropoff_id:
        dropoff_ship = me.get_ship(ship_to_be_dropoff_id)
        dropoff_pos = dropoff_ship.position
        if ship_targets[ship_to_be_dropoff_id] == dropoff_ship.position:
            ready_to_build_dropoff = True
            hack_dropoff = dropoff_pos
            logging.info("Ship {} standby at {} to build dropoff".format(dropoff_ship.id, dropoff_pos))
            if dropoff_ship.halite_amount + game_map[dropoff_ship.position].halite_amount + me.halite_amount >= 4000:
                command_dict[dropoff_ship.id] = dropoff_ship.make_dropoff()
                building_dropoff_this_round = True
                logging.info("Ship {} will be converted to a dropoff at {}".format(dropoff_ship.id, dropoff_pos))

    # 0. Setting targets
    logging.info("#0 Setting targets...")
    # TODO: if game.turn_number > 100:
    targets = [c.position for c in
               get_halite_cells(game.game_map, game.me, map_cells_cache, halite_threshold_end_collect,
                                extra=hack_dropoff)
               if c.position not in ship_targets.values()]

    next_dropoff_candidate = None
    if not (IS_4P and game.game_map.height == 32) and len(me.get_dropoffs()) + 1 in DROPOFF_MIN_SHIP \
            and len(me.get_ships()) > DROPOFF_MIN_SHIP[len(me.get_dropoffs()) + 1] and \
            game.turn_number < MAX_TURN - DROPOFF_MAX_TURN and \
            len(me.get_dropoffs()) < remaining_halite / 22500 / (3.5 if IS_4P else 2) and ship_to_be_dropoff_id is None:
        next_dropoff_candidate = get_dropoff_candidate(game_map, me, IS_4P)
        if next_dropoff_candidate:
            my_ships = sorted(me.get_ships(),
                              key=lambda s: game_map.calculate_distance(s.position, next_dropoff_candidate))
            my_ships = [s for s in my_ships if s.halite_amount < 750]
            ship_to_be_dropoff_id = my_ships[0].id
            ship_targets[ship_to_be_dropoff_id] = next_dropoff_candidate
            hack_dropoff = next_dropoff_candidate
            logging.info("Ship {} is building dropoff at {}".format(ship_to_be_dropoff_id, next_dropoff_candidate))

    dropoff_shipcount = defaultdict(int)
    for id, pos in ship_targets.items():
        nearest_dropoff = get_nearest_dropoff(game_map, me, pos, hack_dropoff)
        dropoff_shipcount[pos_to_hash_key(nearest_dropoff)] += 1

    for ship in me.get_ships():
        # logging.info("Ship {} at {} has {} halite.".format(ship.id, ship.position, ship.halite_amount))
        if ship.id == ship_to_be_dropoff_id:  # wait till enough halite
            if dropoff_candidate_is_valid(game_map, ship_targets[ship_to_be_dropoff_id]):
                # only thing allowed to do is to stall, or go build dropoff
                if not ship.is_full and game_map[ship.position].halite_amount > STALLING_THRESHOLD_HARD:
                    logging.info("Dropoff candidate {} hit hard stalling cell at {}".format(ship.id, ship.position))
                    register_move(ship, Direction.Still, command_dict, game_map)
                else:
                    continue
            else:
                logging.info("Ship {} should no longer build dropoff at {}".format(ship.id, ship_targets[ship.id]))
                ship_targets[ship.id] = try_get_halite_target_nearby(
                    game_map, ship, get_nearest_dropoff(game_map, me, ship.position), ship_targets,
                    halite_threshold_start_collect, BIG_SEARCH_RADIUS)
                if ship.id in command_dict:  # already planned above
                    del command_dict[ship.id]
                ready_to_build_dropoff = False
                building_dropoff_this_round = False
                ship_to_be_dropoff_id = None
                hack_dropoff = None

        if ship.id not in ship_targets:  # new ship - set navigation direction
            # Choose target depending on how crowded the closest dropoff is
            ship_last_dropoff_turn[ship.id] = game.turn_number
            for i in range(len(targets) - 1, 0, -1):
                nearest_dropoff = get_nearest_dropoff(game_map, me, targets[i], hack_dropoff)
                no_of_dropoffs = len(get_dropoff_positions(me))
                weighting = 1.3 * len(me.get_ships()) / no_of_dropoffs
                if no_of_dropoffs > 1 and dropoff_shipcount[pos_to_hash_key(nearest_dropoff)] > weighting:
                    continue
                else:
                    ship_targets[ship.id] = targets.pop(i)
                    break

        nearest_dropoff = get_nearest_dropoff(game_map, me, ship.position, hack_dropoff)
        dist = game_map.calculate_distance(ship.position, nearest_dropoff)
        recall_turns = len(me.get_ships()) / len(get_dropoff_positions(me)) / 4
        if MAX_TURN - game.turn_number - recall_turns - TURNS_TO_RECALL < dist:
            # it's late, ask everyone to come home
            ship_targets[ship.id] = nearest_dropoff
            if dist == 1:  # CRASH
                move = game_map.get_unsafe_moves(ship.position, nearest_dropoff)[0]
                register_move(ship, move, command_dict, game_map)
        elif ship.position == ship_targets[ship.id]:
            # reached target position
            if ship.position in get_dropoff_positions(me):  # reached shipyard, assign new target
                ship_targets[ship.id] = targets.pop()
                # TODO: not using it anyway..
                ship_last_visit = ship_last_dropoff_turn[ship.id] if ship.id in ship_last_dropoff_turn else game.turn_number - 20
                ship_last_dropoff_turn[ship.id] = game.turn_number
                if halite_collection_rate.maxlen <= len(halite_collection_rate):
                    halite_collection_rate.popleft()
                halite_collection_rate.append(ship_prev_halite_amount[ship.id] / (game.turn_number - ship_last_visit))
            elif ship.is_full:
                ship_targets[ship.id] = nearest_dropoff
            else:
                # to detect nearby collided points
                nearby_target = nearest_halite_cell_with_x(game_map, ship.position, {},  # need to be quick
                                                           STALLING_THRESHOLD_HARD, BIG_SEARCH_RADIUS)
                if IS_LATE_GAME and nearby_target and game_map[ship.position].halite_amount < STALLING_THRESHOLD_HARD:
                    if nearby_target in ship_targets.values():
                        # TODO: this is a swap targets function.
                        swap_id = [key for key, value in ship_targets.items() if value == nearby_target][0]
                        swap_ship = me.get_ship(swap_id)
                        if game_map.calculate_distance(nearby_target, ship.position) < \
                                game_map.calculate_distance(nearby_target, swap_ship.position):
                            # swap targets
                            ship_targets[ship.id] = nearby_target
                            new_target = nearest_halite_cell_with_x(game_map, swap_ship.position, ship_targets,
                                                                    halite_threshold_start_collect, search_radius)
                            ship_targets[swap_id] = new_target if new_target else targets.pop()
                        continue
                    else:
                        ship_targets[ship.id] = nearby_target
                        continue

                if game_map[ship.position].halite_amount > halite_threshold_end_collect:
                    register_move(ship, Direction.Still, command_dict, game_map)
                elif ship.halite_amount < SHIP_HOLD_AMOUNT / 2 and not IS_LATE_GAME:  # early game but barely fill
                    new_target = nearest_halite_cell_with_x(game_map, ship.position, ship_targets,
                                                            halite_threshold_start_collect, search_radius)
                    ship_targets[ship.id] = targets.pop() if new_target is None else new_target
                elif ship.halite_amount < SHIP_HOLD_AMOUNT:  # and game.turn_number > EARLY_GAME_TURN:
                    new_target = nearest_halite_cell_with_x(game_map, ship.position, ship_targets,
                                                            halite_threshold_start_collect, search_radius)

                    ship_targets[ship.id] = targets.pop() if new_target is None else new_target
                else:
                    ship_targets[ship.id] = nearest_dropoff
        else:
            # Travelling to target position
            if ship.is_full:
                ship_targets[ship.id] = nearest_dropoff
            else:
                if ship_targets[ship.id] in get_dropoff_positions(me):  # Going home
                    if game_map[ship.position].halite_amount > STALLING_THRESHOLD_SOFT \
                            and ship.halite_amount < SHIP_HOLD_AMOUNT:
                        # more beneficial to stay than travel
                        if ship.id not in stalling_ships:
                            logging.info("Ship {} finds it more beneficial to stall for one round".format(ship.id))
                            register_move(ship, Direction.Still, command_dict, game_map)
                            stalling_ships[ship.id] = ship.position
                        else:
                            del stalling_ships[ship.id]
                            continue
                elif game_map[
                    ship_targets[ship.id]].halite_amount < halite_threshold_start_collect:
                    logging.info("Early game, Ship {}'s target at {} seems to have depleted, reassigning target"
                                 .format(ship.id, ship_targets[ship.id]))
                    new_target = try_get_halite_target_nearby(game_map, ship, nearest_dropoff, ship_targets,
                                                              halite_threshold_start_collect, BIG_SEARCH_RADIUS)
                    ship_targets[ship.id] = targets.pop() if new_target is None else new_target
                elif game_map[ship_targets[ship.id]].halite_amount < 1500 and \
                        (game_map[ship_targets[ship.id]].is_occupied and not me.has_ship(
                            game_map[ship_targets[ship.id]].ship.id)):
                    logging.info("Early game, Ship {}'s target at {} is occupied by opponents, reassigning target"
                                 .format(ship.id, ship_targets[ship.id]))
                    new_target = try_get_halite_target_nearby(game_map, ship, nearest_dropoff, ship_targets,
                                                              halite_threshold_start_collect, BIG_SEARCH_RADIUS)
                    ship_targets[ship.id] = targets.pop() if new_target is None else new_target
                else:
                    # traveling to target halite cell, check if current cell is too occupied
                    # more beneficial to stay than travel
                    if game_map[ship.position].halite_amount > STALLING_THRESHOLD_HARD:
                        logging.info("Ship {} hit hard stalling cell at {}".format(ship.id, ship.position))
                        register_move(ship, Direction.Still, command_dict, game_map)
                    elif game_map[ship.position].halite_amount > STALLING_THRESHOLD_SOFT:
                        if ship.id not in stalling_ships:
                            logging.info("Ship {} finds it more beneficial to stall for one round".format(ship.id))
                            register_move(ship, Direction.Still, command_dict, game_map)
                            stalling_ships[ship.id] = ship.position
                        else:
                            del stalling_ships[ship.id]
                            continue
                    elif IS_LATE_GAME:
                        # to detect nearby collided points
                        nearby_target = nearest_halite_cell_with_x(game_map, ship.position, {},  # need to be quick
                                                                   STALLING_THRESHOLD_HARD, BIG_SEARCH_RADIUS)
                        if nearby_target:
                            if nearby_target in ship_targets.values():
                                # TODO: this is a swap targets function.
                                swap_id = [key for key, value in ship_targets.items() if value == nearby_target][0]
                                swap_ship = me.get_ship(swap_id)
                                if game_map.calculate_distance(nearby_target, ship.position) < \
                                        game_map.calculate_distance(nearby_target, swap_ship.position):
                                    # swap targets
                                    ship_targets[ship.id] = nearby_target
                                    new_target = nearest_halite_cell_with_x(game_map, swap_ship.position, ship_targets,
                                                                            halite_threshold_start_collect, search_radius)
                                    ship_targets[swap_id] = new_target if new_target else targets.pop()
                            else:
                                ship_targets[ship.id] = nearby_target

        logging.info("Ship {} at {} has target {} ".format(ship.id, ship.position, ship_targets[ship.id]))

    # 1. Finding potential moves (has energy, will include blocked for resolution)
    # TODO: account for enemies!
    logging.info("#1 Finding all potential moves...")

    for ship in me.get_ships():
        if ship.id in command_dict:
            continue  # already assigned, e.g. stalling

        enemies = enemy_within_distance(me, game_map, ship.position, 2)
        allies = ally_within_distance(me, game_map, ship.position, 2)

        if ship.id in ship_planned_moves and ship_planned_moves[ship.id]:
            logging.info('Ship {} has planned move: {}'.format(ship.id, ship_planned_moves[ship.id]))
            if ship.halite_amount >= .1 * game_map[ship.position].halite_amount:
                possible_moves = [ship_planned_moves[ship.id].pop(0)]
            else:
                possible_moves = []
        else:
            possible_moves = get_possible_moves(ship_targets[ship.id], ship, game_map, me)

            # opening: make ways, not very effective
            if ship.position == me.shipyard.position and game.turn_number < 6:
                possible_moves.extend([d for d in Direction.get_all_cardinals()
                                       if d not in possible_moves
                                       and not game_map[ship.position.directional_offset(d)].is_occupied])

            if len(possible_moves) == 1:
                blocked_move = possible_moves[0]
                p = game_map.normalize(ship.position.directional_offset(blocked_move))
                # try move sideways if the only possible move is blocked by enemy, or a ship staying more than one turn
                if game_map[p].is_occupied: # and ship.halite_amount > 300:
                    if not me.has_ship(game_map[p].ship.id):
                        side_moves = [d for d in Direction.get_all_cardinals()
                                      if d not in possible_moves
                                      and not game_map[ship.position.directional_offset(d)].is_occupied
                                      and d != Direction.invert(blocked_move)]
                        for s in side_moves:
                            next_next_pos = ship.position.directional_offset(s).directional_offset(blocked_move)
                            if not game_map[next_next_pos].is_occupied:
                                logging.info('Ship {} is blocked and will move ({},{},{})'.
                                             format(ship.id, s, blocked_move, blocked_move))
                                ship_planned_moves[ship.id] = [blocked_move, blocked_move]
                                possible_moves = [s]
                                break
                    elif p == ship_targets[game_map[p].ship.id] and not IS_LATE_GAME and get_ship_remaining_turns(
                            me, game_map, game_map[p].ship, halite_threshold_end_collect) > 1:
                        # blocked by own ship, swap targets
                        logging.info('Ship {} is blocked by {} so they are swapping targets'.
                                     format(ship.id, game_map[p].ship.id))
                        my_target = ship_targets[ship.id]
                        ship_targets[game_map[p].ship.id] = my_target
                        ship_targets[ship.id] = p

        # Avoid crashing opponents in 4p
        if ship.halite_amount > 300 or len(enemies) > len(allies):  # and is_4p:
            logging.info("Before resolution/prediction, Ship {} has {} possible moves".format(ship.id, len(possible_moves)))
            possible_moves = [p for p in possible_moves if game_map.normalize(ship.position.directional_offset(p))
                              not in enemies_predicted_targets.values()]
            logging.info("{} has {} possible moves after accounting for enemy".format(ship.id, len(possible_moves)))

        for m in possible_moves:
            p = game_map.normalize(ship.position.directional_offset(m))

            if not game_map[p].is_occupied:
                logging.info("Ship {} can FREELY go {} to {}".format(ship.id, m, p))
                continue
            elif me.has_ship(game_map[p].ship.id):
                # one of our own ships that can be resolved
                target_count[pos_to_hash_key(p)] += 1
                logging.info("Ship {} can go {} to {}".format(ship.id, m, p))
            else:
                # enemy ship
                dropoff_areas = [get_surrounding_cells(game_map, dropoff, 2) for dropoff in get_dropoff_positions(me)]
                enemy_halite_amount = game_map[p].ship.halite_amount + game_map[p].halite_amount
                our_halite_amount = ship.halite_amount + game_map[ship.position].halite_amount
                if (not IS_4P and enemy_halite_amount > our_halite_amount) \
                        or p in [cell.position for dropoff_area in dropoff_areas for cell in dropoff_area]\
                        or (not IS_4P and len(enemies) < len(allies)):
                    # (try to) crash enemy ship if it has more halite than us or occupying our shipyard
                    logging.info("Ship {} has found an enemy ship to crash!")
                    register_move(ship, m, command_dict, game_map)
                    break
                # TODO: fleeing if we have less ship, move sideways should work better?
                # elif not is_4p and len(me.get_ships()) < len(opponents[1].get_ships()):
                #     logging.info("Ship {} is fleeing from enemy!")
                #     inv_m = Direction.invert(m)
                #     inv_p = ship.position.directional_offset(inv_m)
                #     if not game_map[inv_p].is_occupied:
                #         register_move(ship, inv_m, command_dict, game_map)
                #     if pos_to_hash_key(inv_p) in nextpos_ship:
                #         del nextpos_ship[pos_to_hash_key(inv_p)]
                #     break

        if ship.id not in command_dict:  # not assigned yet
            pos_and_moves = [(game_map.normalize(ship.position.directional_offset(m)), m) for m in possible_moves
                             if not game_map[ship.position.directional_offset(m)].is_occupied or me.has_ship(
                    game_map[ship.position.directional_offset(m)].ship.id)]  # filter out enemy ships
            logging.info("Ship {} has {} possible moves".format(ship.id, len(possible_moves)))
            graph[ship.id] = ShipPlan(ship, pos_and_moves)

    # 2. Resolve possible collisions, starting from blocked cells
    # then by cells targeted by only one ship, (sort by number of ships)
    logging.info("#2 Resolving moves...")
    graph_ordered = OrderedDict(sorted(graph.items(), key=lambda x: (x[1][0].halite_amount, len(x[1][1]),
                                                                     target_count[pos_to_hash_key(x[1][1][0][0] if len(
                                                                         x[1][1]) > 0 else None)])))
    logging.info("graph_ordered dictionary {}".format(graph_ordered))

    for ship_id in graph_ordered:
        resolve_moves_recursive([], ship_id, graph_ordered, command_dict, game_map)

    # Queue up commands
    for k, v in command_dict.items():
        command_queue.append(v)

    dropoff_cost = 0
    if building_dropoff_this_round:
        ship = game.me.get_ship(ship_to_be_dropoff_id)
        absorbed = ship.halite_amount + game_map[ship.position].halite_amount
        dropoff_cost = 4000 - absorbed
        logging.info("Building dropoff: absorbed {}".format(absorbed))
        ship_to_be_dropoff_id = None

    pause_ship_production = ship_to_be_dropoff_id and ready_to_build_dropoff

    avg_rate = sum(halite_collection_rate) / (len(halite_collection_rate) + 1)  # just hacking div by 0 away
    logging.info("Average H/turn by last 10 ships: {}".format(avg_rate))

    # TODO: factor the rate of halite depletion into avg_rate reduction, not constant
    # TODO: maybe try to use that in collection threshold and discount cost first
    tweaking_constant = 1 / .8E6
    # if (game.turn_number < 200 or avg_rate * .5 * (MAX_TURN - game.turn_number) > 1000) and \
    if len(me.get_ships()) < remaining_halite * (MAX_TURN - game.turn_number) * tweaking_constant and \
            me.halite_amount - dropoff_cost >= constants.SHIP_COST and game.turn_number < MAX_TURN - SHIP_MAX_TURN and \
            not game_map[me.shipyard].is_occupied and not pause_ship_production:
        command_queue.append(me.shipyard.spawn())

    # Send your moves back to the game environment, ending this turn.
    game.end_turn(command_queue)
