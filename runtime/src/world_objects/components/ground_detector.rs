use rapier2d::prelude::*;

#[derive(Clone, Default)]
pub struct GroundDetector {
    pub ray_offset_inward: f32,
    pub ray_y_offset: f32,
    pub max_toi: f32,
}

impl GroundDetector {
    pub fn new(ray_offset_inward: f32, ray_y_offset: f32, max_toi: f32) -> Self {
        GroundDetector {
            ray_offset_inward,
            ray_y_offset,
            max_toi,
        }
    }

    pub fn check_grounded(
        &self,
        player_pos: &Vector<f32>,
        width: f32,
        height: f32,
        rigid_body_set: &RigidBodySet,
        collider_set: &ColliderSet,
        query_pipeline: &QueryPipeline,
        self_handle: RigidBodyHandle,
    ) -> bool {
        let left_x = player_pos.x - width / 2.0 + self.ray_offset_inward;
        let right_x = player_pos.x + width / 2.0 - self.ray_offset_inward;
        let ray_y = player_pos.y - height / 2.0 + self.ray_y_offset;

        let ray_dir = vector![0.0, -1.0];
        let filter = QueryFilter::default().exclude_rigid_body(self_handle);

        let hit_left = query_pipeline.cast_ray(
            rigid_body_set,
            collider_set,
            &Ray::new(point![left_x, ray_y], ray_dir),
            self.max_toi,
            true,
            filter,
        );

        let hit_right = query_pipeline.cast_ray(
            rigid_body_set,
            collider_set,
            &Ray::new(point![right_x, ray_y], ray_dir),
            self.max_toi,
            true,
            filter,
        );

        hit_left.is_some() || hit_right.is_some()
    }
}
