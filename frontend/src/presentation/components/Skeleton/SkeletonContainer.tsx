import { Skeleton } from "./Skeleton"
import type { SkeletonProps } from "./SkeletonConfig"

function SkeletonContainer(props: SkeletonProps) {
  return <Skeleton {...props} />
}

export { SkeletonContainer }
